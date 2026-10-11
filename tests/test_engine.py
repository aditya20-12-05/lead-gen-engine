import json
from email.message import EmailMessage

import pytest

from engine import create_app, db, drafts, importers, mailer, rules, seed, sources

SETTINGS = {"sender_name": "Test Founder", "sender_title": "Founder, SELEQT Private Wealth", "footer": "Ahmedabad, India"}
MAIL = mailer.MailConfig(
    user="ishit@seleqtwealth.in", password="x", smtp_host="smtp.test", smtp_port=465,
    imap_host="imap.test", imap_port=993, sent_folder=None, from_name="Test Founder",
)


@pytest.fixture
def app(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(SETTINGS))
    app = create_app(tmp_path / "engine.db", settings_path)
    app.config.update(TESTING=True, MAIL_CONFIG=lambda s: MAIL, SENT=[])

    def fake_send(config, msg):
        app.config["SENT"].append(msg)
        return msg["Message-ID"]

    app.config["MAIL_SEND"] = fake_send
    with db.connect(app.config["DB_PATH"]) as conn:
        seed.seed(conn)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def conn(app):
    c = db.connect(app.config["DB_PATH"])
    yield c
    c.close()


def task_id(conn, org_name):
    return conn.execute(
        "SELECT t.id FROM tasks t JOIN organisations g ON g.id = t.org_id WHERE g.name = ?", (org_name,)
    ).fetchone()["id"]


def org_id(conn, name):
    return conn.execute("SELECT id FROM organisations WHERE name = ?", (name,)).fetchone()["id"]


def make_draft(client, tid, kind="invite", template="template", language="en"):
    resp = client.post(f"/tasks/{tid}/draft", data={"kind": kind, "template": template, "language": language})
    location = resp.headers.get("Location", "")
    return int(location.rsplit("/", 1)[1]) if "/outreach/" in location else None


def send(client, did, reviewed="yes"):
    return client.post(f"/outreach/{did}/send", data={"reviewed": reviewed})


def sent_at(conn, did):
    return conn.execute("SELECT sent_at FROM outreach WHERE id = ?", (did,)).fetchone()["sent_at"]


# Structure

def test_seed_builds_countries_approaches_and_tasks(conn):
    approaches = {(r["country"], r["name"]) for r in conn.execute("SELECT country, name FROM approaches")}
    assert ("GB", "Weekly newspaper column") in approaches
    assert ("AE", "Community webinars") in approaches
    brief = conn.execute("SELECT our_brief FROM approaches WHERE country = 'GB'").fetchone()["our_brief"]
    assert "trial piece" in brief and "weekly series" in brief
    assert conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == 9


def test_pages_render(client, conn):
    gb = conn.execute("SELECT id FROM approaches WHERE country = 'GB'").fetchone()["id"]
    for path in ["/", "/countries/GB", f"/approaches/{gb}", f"/tasks/{task_id(conn, 'Gujarati Samaj UAE')}",
                 "/orgs", f"/orgs/{org_id(conn, 'Gujarati Samaj UAE')}", "/events", "/enquiries", "/dnc"]:
        assert client.get(path).status_code == 200, path


def test_uk_task_without_email_cannot_be_drafted_until_email_added(client, conn):
    tid = task_id(conn, "Garavi Gujarat (Asian Media Group)")
    assert make_draft(client, tid, template="blank") is None
    client.post(f"/tasks/{tid}", data={"contact_email": "Editor@Example.co.uk", "source_note": "note", "plan": "", "owner": "Team"})
    did = make_draft(client, tid, template="blank")
    assert did is not None
    body = conn.execute("SELECT body FROM outreach WHERE id = ?", (did,)).fetchone()["body"]
    assert "[Write your email here]" in body and "Test Founder" in body


def test_add_task_with_new_organisation_needs_source(client, conn):
    gb = conn.execute("SELECT id FROM approaches WHERE country = 'GB'").fetchone()["id"]
    client.post(f"/approaches/{gb}", data={"action": "add_task", "name": "No Source Weekly", "kind": "media"})
    assert conn.execute("SELECT count(*) FROM organisations WHERE name = 'No Source Weekly'").fetchone()[0] == 0
    client.post(f"/approaches/{gb}", data={"action": "add_task", "name": "Leicester Weekly", "kind": "media",
                                           "source_url": "https://example.org", "contact_email": "news@example.org"})
    assert conn.execute(
        "SELECT count(*) FROM tasks t JOIN organisations g ON g.id = t.org_id WHERE g.name = 'Leicester Weekly'"
    ).fetchone()[0] == 1


# Templates and copy checks

def test_house_style_flags_dashes_and_lowercase_brand():
    issues = rules.house_style_issues("Seleqt helps — really – a lot")
    assert any("em dash" in i for i in issues)
    assert any("en dash" in i for i in issues)
    assert any("SELEQT" in i for i in issues)
    assert rules.house_style_issues("SELEQT, (in capitals), with commas") == []


def test_sebi_red_flags():
    assert rules.compliance_issues("Assured returns with no risk")
    assert rules.compliance_issues("Purely educational session") == []


@pytest.mark.parametrize("key", list(drafts.TEMPLATES))
def test_every_template_passes_copy_checks_and_is_in_founder_voice(key):
    kind, language = key
    subject, body = drafts.render_invite({"name": "Example Samaj", "kind": kind}, language, SETTINGS)
    assert rules.copy_issues(subject + "\n" + body) == []
    assert "SELEQT" in body and "Test Founder" in body


# Sending from the mailbox

def test_send_requires_review_tick_and_clean_copy(client, conn, app):
    did = make_draft(client, task_id(conn, "Gujarati Samaj Qatar"))
    send(client, did, reviewed="")
    assert sent_at(conn, did) is None
    client.post(f"/outreach/{did}", data={"subject": "Guaranteed returns", "body": "Seleqt — hello"})
    send(client, did)
    assert sent_at(conn, did) is None
    assert app.config["SENT"] == []


def test_send_delivers_from_founder_mailbox_and_records_message_id(client, conn, app):
    did = make_draft(client, task_id(conn, "Gujarati Samaj UAE"))
    send(client, did)
    row = conn.execute("SELECT * FROM outreach WHERE id = ?", (did,)).fetchone()
    assert row["sent_at"] and row["sent_by"] == "ishit@seleqtwealth.in"
    msg = app.config["SENT"][0]
    assert msg["To"] == "gujaratisamajemirates@gmail.com"
    assert "ishit@seleqtwealth.in" in msg["From"] and row["message_id"] == msg["Message-ID"]


def test_failed_send_is_not_marked_sent(client, conn, app):
    def broken(config, msg):
        raise OSError("connection refused")

    app.config["MAIL_SEND"] = broken
    did = make_draft(client, task_id(conn, "Gujarati Samaj UAE"))
    send(client, did)
    assert sent_at(conn, did) is None


def test_send_blocked_when_mailbox_not_connected(client, conn, app):
    app.config["MAIL_CONFIG"] = lambda s: None
    did = make_draft(client, task_id(conn, "Gujarati Samaj UAE"))
    send(client, did)
    assert sent_at(conn, did) is None


# Nobody contacted twice, do not contact

def test_one_first_email_per_organisation_ever(client, conn):
    tid = task_id(conn, "Gujarati Samaj UAE")
    send(client, make_draft(client, tid))
    assert make_draft(client, tid) is None


def test_same_email_in_another_approach_is_still_blocked(client, conn):
    send(client, make_draft(client, task_id(conn, "Gujarati Samaj UAE")))
    gb = conn.execute("SELECT id FROM approaches WHERE country = 'GB'").fetchone()["id"]
    client.post(f"/approaches/{gb}", data={"action": "add_task", "name": "Same Inbox", "kind": "media",
                                           "source_url": "https://x", "contact_email": "gujaratisamajemirates@gmail.com"})
    assert make_draft(client, task_id(conn, "Same Inbox"), template="blank") is None


def test_dnc_blocks_drafting_and_cannot_block_webmail(client, conn):
    with pytest.raises(rules.RuleViolation):
        rules.add_dnc(conn, "domain", "gmail.com", "too broad")
    rules.add_dnc(conn, "email", "Gujarati.Samaj.Qatar@gmail.com", "asked not to be contacted")
    assert make_draft(client, task_id(conn, "Gujarati Samaj Qatar")) is None


def test_dnc_has_no_delete_route(client):
    assert client.delete("/dnc").status_code == 405


# Catching replies

class FakeIMAP:
    def __init__(self, messages):
        self.messages = messages

    def login(self, user, password):
        pass

    def select(self, mailbox, readonly=False):
        assert readonly
        return "OK", [b"1"]

    def search(self, charset, *criteria):
        sender = criteria[1].strip('"')
        nums = [str(i + 1).encode() for i, m in enumerate(self.messages) if sender in m["From"].lower()]
        return "OK", [b" ".join(nums)]

    def fetch(self, num, spec):
        assert "PEEK" in spec
        return "OK", [(b"1", self.messages[int(num) - 1].as_bytes())]

    def logout(self):
        pass


def reply(sender, body, message_id="<r1@example.com>", subject="Re: session"):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = sender, "ishit@seleqtwealth.in", subject, message_id
    m.set_content(body)
    return m


def test_replies_are_caught_once_and_unlock_a_reply_draft(client, conn, app):
    tid = task_id(conn, "Gujarati Samaj UAE")
    send(client, make_draft(client, tid))
    imap = FakeIMAP([reply("Committee <gujaratisamajemirates@gmail.com>", "Yes, please propose a date in November.")])
    assert mailer.fetch_replies(conn, MAIL, imap_factory=lambda: imap) == {"new": 1, "opt_outs": []}
    assert mailer.fetch_replies(conn, MAIL, imap_factory=lambda: imap)["new"] == 0  # no duplicates
    rid = make_draft(client, tid, kind="reply")
    assert rid is not None
    client.post(f"/outreach/{rid}", data={"subject": "Re: session", "body": "Thank you. How about 21 November?\n\nTest Founder"})
    send(client, rid)
    assert sent_at(conn, rid)
    assert app.config["SENT"][-1]["In-Reply-To"] == "<r1@example.com>"


def test_opt_out_reply_goes_on_do_not_contact(client, conn):
    send(client, make_draft(client, task_id(conn, "Gujarati Samaj Qatar")))
    imap = FakeIMAP([reply("gujarati.samaj.qatar@gmail.com", "Please remove us from your list.")])
    result = mailer.fetch_replies(conn, MAIL, imap_factory=lambda: imap)
    assert result["opt_outs"] == ["gujarati.samaj.qatar@gmail.com"]
    assert rules.dnc_reason(conn, email="gujarati.samaj.qatar@gmail.com")


def test_mail_from_strangers_is_ignored(conn, client):
    send(client, make_draft(client, task_id(conn, "Gujarati Samaj UAE")))
    imap = FakeIMAP([reply("someone.else@example.com", "hello")])
    assert mailer.fetch_replies(conn, MAIL, imap_factory=lambda: imap)["new"] == 0


# Registrations and follow-up

CSV = """name,email,country,consent_followup,consent_text
Asha Example,asha@example.com,GB,yes,I agree to one follow-up email about this session
Ravi Example,ravi@example.com,AE,yes,I agree to one follow-up email about this session
Mina Example,mina@example.com,AU,no,Joining details only
Bad Row,not-an-email,GB,yes,x
"""


def add_event(conn):
    conn.execute(
        "INSERT INTO events (title, starts_at, language, cohort, created_at) VALUES ('t', 's', 'English', 'c', ?)",
        (db.now(),),
    )
    conn.commit()


def test_import_and_followup_rules(conn):
    add_event(conn)
    rules.add_dnc(conn, "email", "blocked@example.com", "opted out")
    report = importers.import_registrations(conn, 1, CSV + "Blocked Person,blocked@example.com,GB,yes,I agree\n")
    assert report == {"added": 3, "duplicate": 0, "do_not_contact": 1, "invalid": [5]}
    regs = {r["email"]: r for r in conn.execute("SELECT * FROM registrations")}
    assert rules.followup_allowed(regs["asha@example.com"])
    assert not rules.followup_allowed(regs["ravi@example.com"])  # Gulf resident
    assert not rules.followup_allowed(regs["mina@example.com"])  # no consent


def test_followup_only_once(client, conn):
    add_event(conn)
    importers.import_registrations(conn, 1, CSV)
    rid = conn.execute("SELECT id FROM registrations WHERE email = 'asha@example.com'").fetchone()["id"]
    client.post(f"/registrations/{rid}/followed-up")
    reg = conn.execute("SELECT * FROM registrations WHERE id = ?", (rid,)).fetchone()
    assert reg["followed_up_at"] and not rules.followup_allowed(reg)


# Enquiries

def enquiry(client, **overrides):
    data = {
        "initiated_by_client": "yes", "name": "Kiran Example", "email": "kiran@example.com",
        "country": "GB", "family_key": "example family", "route": "RIA",
        "first_message": "Hello, I read your column and would like to talk about returning to India.",
    }
    data.update(overrides)
    return client.post("/enquiries", data=data)


def test_enquiry_requires_client_initiative_and_first_message(client, conn):
    enquiry(client, initiated_by_client="")
    enquiry(client, first_message=" ")
    assert conn.execute("SELECT count(*) FROM enquiries").fetchone()[0] == 0
    enquiry(client)
    assert conn.execute("SELECT count(*) FROM enquiries").fetchone()[0] == 1


def test_family_stays_on_one_side(client, conn):
    enquiry(client)
    enquiry(client, name="Spouse Example", email="spouse@example.com", route="MFD")
    assert conn.execute("SELECT count(*) FROM enquiries").fetchone()[0] == 1


# Source health

def test_source_check_records_exact_status(conn):
    count = conn.execute("SELECT count(*) FROM organisations").fetchone()[0]
    statuses = iter(["ok 200", "http 404", "error: timed out"] * count)
    results = sources.check_all(conn, fetch=lambda url: next(statuses))
    stored = [r["source_status"] for r in conn.execute("SELECT source_status FROM organisations ORDER BY id")]
    assert stored == [s for _, _, s in results]


def test_migration_adds_columns_to_old_database(tmp_path):
    path = tmp_path / "old.db"
    old = db.connect(path)
    old.executescript("""
        CREATE TABLE outreach (id INTEGER PRIMARY KEY, org_id INTEGER, kind TEXT, language TEXT,
            subject TEXT, body TEXT, drafted_at TEXT, sent_at TEXT, sent_by TEXT);
        CREATE TABLE inbound (id INTEGER PRIMARY KEY, org_id INTEGER, received_at TEXT, channel TEXT, body TEXT);
    """)
    db.init(old)
    cols = {r["name"] for r in old.execute("PRAGMA table_info(inbound)")}
    assert {"task_id", "message_id", "from_addr", "subject"} <= cols
    old.close()
