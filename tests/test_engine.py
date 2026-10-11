import json
import os
from email.message import EmailMessage

import pytest

from engine import create_app, db, drafts, finder, importers, mailer, rules, seed, sources

SETTINGS = {"sender_name": "Test Founder", "sender_title": "Founder, SELEQT Private Wealth", "footer": "Ahmedabad, India"}
MAIL = mailer.MailConfig(
    user="ishit@seleqtwealth.in", password="x", smtp_host="smtp.test", smtp_port=465,
    imap_host="imap.test", imap_port=993, sent_folder=None, from_name="Test Founder",
)
PG_URL = os.environ.get("TEST_DATABASE_URL")


class FakeSMTP:
    def __init__(self, outbox, fail=False):
        self.outbox, self.fail = outbox, fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        if self.fail:
            raise OSError("connection refused")

    def send_message(self, msg):
        self.outbox.append(msg)


class FakeIMAP:
    def __init__(self, messages=None):
        self.messages = messages or []

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


def set_mailbox(app, box):
    app.config["MAILBOX"] = lambda settings: box
    app.extensions.pop("mailbox", None)


@pytest.fixture(params=["sqlite", "postgres"])
def target(request, tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in [k for k in os.environ if k.startswith("SELEQT_")]:
        monkeypatch.delenv(key)
    if request.param == "sqlite":
        return str(tmp_path / "engine.db")
    if not PG_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg

    with psycopg.connect(PG_URL, autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
    return PG_URL


@pytest.fixture
def app(target, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(SETTINGS))
    app = create_app(target, settings_path)
    app.config.update(TESTING=True, SENT=[], IMAP=FakeIMAP())
    set_mailbox(app, mailer.SmtpMailbox(MAIL, imap_factory=lambda: app.config["IMAP"],
                                        smtp_factory=lambda: FakeSMTP(app.config["SENT"])))
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


def make_draft(client, tid, kind="invite", template="template", language="en", channel="email"):
    resp = client.post(f"/tasks/{tid}/draft", data={"kind": kind, "template": template, "language": language, "channel": channel})
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


def test_uk_task_uses_contact_form_when_there_is_no_email(client, conn, app):
    tid = task_id(conn, "Garavi Gujarat (Asian Media Group)")
    assert make_draft(client, tid, template="blank") is None  # email channel: no email recorded
    did = make_draft(client, tid, template="blank", channel="contact_form")
    row = conn.execute("SELECT * FROM outreach WHERE id = ?", (did,)).fetchone()
    assert row["channel"] == "contact_form" and "Ishit Lakhani" not in row["body"]  # settings file wins
    assert "Test Founder" in row["body"]
    client.post(f"/outreach/{did}", data={"subject": "", "body": "Dear Editor, a weekly column offer.\n\nTest Founder"})
    send(client, did)  # only email can be sent from the engine
    assert sent_at(conn, did) is None and app.config["SENT"] == []
    client.post(f"/outreach/{did}/sent", data={"sent_by": "Team member"})
    assert sent_at(conn, did)
    # Nobody contacted twice, whatever the channel.
    client.post(f"/tasks/{tid}", data={"contact_email": "editor@example.co.uk", "source_note": "", "plan": "", "owner": ""})
    assert make_draft(client, tid, template="blank") is None


def test_organisation_with_no_contact_route_needs_contact(client, conn):
    tid = task_id(conn, "Shri Gujarati Samaj Bahrain")
    assert "needs contact" in client.get(f"/tasks/{tid}").get_data(as_text=True)
    assert make_draft(client, tid, channel="whatsapp") is None
    client.post(f"/tasks/{tid}", data={"contact_phone": "+973 0000 0000", "source_note": "", "plan": "", "owner": ""})
    assert make_draft(client, tid, channel="whatsapp") is not None


def test_default_sender_and_mailbox_choice(monkeypatch):
    assert drafts.DEFAULT_SETTINGS["sender_name"] == "Ishit Lakhani"
    for key in [k for k in os.environ if k.startswith("SELEQT_")]:
        monkeypatch.delenv(key)
    assert mailer.mailbox_from_env() is None
    monkeypatch.setenv("SELEQT_MAIL_PASSWORD", "x")
    box = mailer.mailbox_from_env("Ishit Lakhani")
    assert isinstance(box, mailer.SmtpMailbox)
    assert (box.user, box.config.smtp_host, box.config.imap_host) == ("ishit@seleqtwealth.in", "smtp.zoho.in", "imap.zoho.in")
    for key, value in {"SELEQT_ZOHO_CLIENT_ID": "a", "SELEQT_ZOHO_CLIENT_SECRET": "b", "SELEQT_ZOHO_REFRESH_TOKEN": "c"}.items():
        monkeypatch.setenv(key, value)
    box = mailer.mailbox_from_env("Ishit Lakhani")
    assert isinstance(box, mailer.ZohoMailbox) and box.config.mail_url == "https://mail.zoho.in"


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
    set_mailbox(app, mailer.SmtpMailbox(MAIL, smtp_factory=lambda: FakeSMTP([], fail=True)))
    did = make_draft(client, task_id(conn, "Gujarati Samaj UAE"))
    send(client, did)
    assert sent_at(conn, did) is None


def test_send_blocked_when_mailbox_not_connected(client, conn, app):
    set_mailbox(app, None)
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

def reply(sender, body, message_id="<r1@example.com>", subject="Re: session"):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = sender, "ishit@seleqtwealth.in", subject, message_id
    m.set_content(body)
    return m


def test_replies_are_caught_once_and_unlock_a_reply_draft(client, conn, app):
    tid = task_id(conn, "Gujarati Samaj UAE")
    send(client, make_draft(client, tid))
    app.config["IMAP"].messages = [reply("Committee <gujaratisamajemirates@gmail.com>", "Yes, please propose a date in November.")]
    box = app.config["MAILBOX"](SETTINGS)
    assert box.fetch_replies(conn) == {"new": 1, "opt_outs": []}
    assert box.fetch_replies(conn)["new"] == 0  # no duplicates
    rid = make_draft(client, tid, kind="reply")
    assert rid is not None
    client.post(f"/outreach/{rid}", data={"subject": "Re: session", "body": "Thank you. How about 21 November?\n\nTest Founder"})
    send(client, rid)
    assert sent_at(conn, rid)
    assert app.config["SENT"][-1]["In-Reply-To"] == "<r1@example.com>"


def test_opt_out_reply_goes_on_do_not_contact(client, conn, app):
    send(client, make_draft(client, task_id(conn, "Gujarati Samaj Qatar")))
    app.config["IMAP"].messages = [reply("gujarati.samaj.qatar@gmail.com", "Please remove us from your list.")]
    result = app.config["MAILBOX"](SETTINGS).fetch_replies(conn)
    assert result["opt_outs"] == ["gujarati.samaj.qatar@gmail.com"]
    assert rules.dnc_reason(conn, email="gujarati.samaj.qatar@gmail.com")


def test_mail_from_strangers_is_ignored(conn, client, app):
    send(client, make_draft(client, task_id(conn, "Gujarati Samaj UAE")))
    app.config["IMAP"].messages = [reply("someone.else@example.com", "hello")]
    assert app.config["MAILBOX"](SETTINGS).fetch_replies(conn)["new"] == 0


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


# Task lists use the organisation's own id, not the task's

def test_task_lists_use_the_right_organisation(client, conn):
    client.post("/orgs", data={"name": "Orphan Org", "kind": "media", "country": "GB", "source_url": "https://o"})
    gb = conn.execute("SELECT id FROM approaches WHERE country = 'GB'").fetchone()["id"]
    client.post(f"/approaches/{gb}", data={"action": "add_task", "name": "Leicester Weekly", "kind": "media",
                                           "source_url": "https://l", "contact_email": "news@leicester.example"})
    tid = task_id(conn, "Leicester Weekly")
    assert tid != org_id(conn, "Leicester Weekly")
    page = client.get(f"/approaches/{gb}").get_data(as_text=True)
    row = page[page.index(f"/tasks/{tid}"):][:400]
    assert "news@leicester.example" in row and ">ready<" in row


# Secret link

def test_secret_link_gates_every_page(target, tmp_path):
    app = create_app(target, tmp_path / "none.json", access_key="s3cret-link")
    client = app.test_client()
    assert client.get("/").status_code == 404
    assert client.get("/healthz").status_code == 200
    assert client.get("/?key=wrong").status_code == 404
    resp = client.get("/calendar?key=s3cret-link")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/calendar")
    assert client.get("/calendar").status_code == 200  # cookie set
    assert client.get("/").headers["X-Robots-Tag"] == "noindex, nofollow"


# Contact finder

PAGES = {
    "https://samaj.example/": '<a href="/contact-us">Contact</a> <a href="https://www.facebook.com/samaj">FB</a>'
                              '<a href="https://www.facebook.com/sharer/sharer.php?u=x">share</a> logo@2x.png',
    "https://samaj.example/contact-us": '<a href="mailto:Committee@Samaj.example?subject=Hi">mail</a>'
                                        '<a href="tel:+971 4 123 4567">call</a><form action="/send"></form>'
                                        'Write to info@samaj.example or user@example.com',
}


def test_contact_finder_suggests_and_applies(client, conn, app):
    oid = org_id(conn, "Gujarati Samaj Qatar")
    conn.execute("UPDATE organisations SET website = 'https://samaj.example/' WHERE id = ?", (oid,))
    conn.commit()
    app.config["FETCH_PAGE"] = lambda url: PAGES[url]
    client.post(f"/orgs/{oid}/find-contacts")
    found = {(r["kind"], r["value"]) for r in conn.execute("SELECT kind, value FROM contact_suggestions WHERE org_id = ?", (oid,))}
    assert found == {("email", "committee@samaj.example"), ("email", "info@samaj.example"),
                     ("phone", "+971 4 123 4567"), ("social", "https://www.facebook.com/samaj"),
                     ("contact_form", "https://samaj.example/contact-us")}
    sid = conn.execute("SELECT id FROM contact_suggestions WHERE kind = 'phone'").fetchone()["id"]
    client.post(f"/suggestions/{sid}", data={"action": "use"})
    assert conn.execute("SELECT contact_phone FROM organisations WHERE id = ?", (oid,)).fetchone()[0] == "+971 4 123 4567"


def test_contact_finder_reports_unreadable_sites(conn):
    def down(url):
        raise OSError("unreachable")

    org = conn.execute("SELECT * FROM organisations WHERE name = 'Gujarati Samaj UAE'").fetchone()
    result = finder.run_for_org(conn, org, fetch=down)
    assert result["added"] == 0 and "unreachable" in result["errors"][0]


# Results and calendar

def test_results_count_contacts_outcomes_and_qualified_enquiries(client, conn):
    tid = task_id(conn, "Gujarati Samaj UAE")
    send(client, make_draft(client, tid))
    client.post(f"/tasks/{tid}", data={"contact_email": "gujaratisamajemirates@gmail.com", "source_note": "",
                                        "plan": "", "owner": "", "outcome": "agreed"})
    enquiry(client, country="AE", ticket_fit="lump_sum", source_org_id=org_id(conn, "Gujarati Samaj UAE"))
    import re

    page = client.get("/results").get_data(as_text=True)
    row = page[page.index("Community webinars"):page.index("</tr>", page.index("Community webinars"))]
    cells = re.findall(r"<td>(?:<strong>)?(\d+)", row)
    # targets, contacted, replied, agreed, live, declined, enquiries, qualified
    assert cells == ["2", "1", "0", "1", "0", "0", "1", "1"]


def test_calendar_shows_festivals_task_steps_and_reminders(client, conn):
    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=2)).isoformat()
    tid = task_id(conn, "Gujarati Samaj UAE")
    client.post(f"/tasks/{tid}", data={"contact_email": "gujaratisamajemirates@gmail.com", "source_note": "",
                                        "plan": "", "owner": "", "outcome": "open",
                                        "next_action": "Propose November date", "next_action_date": soon})
    client.post("/calendar", data={"date": soon, "title": "Draft first UK column", "kind": "deadline"})
    calendar = client.get("/calendar").get_data(as_text=True)
    assert "Diwali" in calendar and "Propose November date" in calendar and "Draft first UK column" in calendar
    overview = client.get("/").get_data(as_text=True)
    assert "Propose November date" in overview and "Draft first UK column" in overview


# Zoho Mail API

class FakeZoho:
    def __init__(self, messages=()):
        self.calls, self.messages = [], list(messages)

    def __call__(self, method, url, data=None, headers=None, form=False):
        self.calls.append((method, url, data))
        if url.endswith("/oauth/v2/token"):
            assert form and data["grant_type"] == "refresh_token"
            return {"access_token": "tok", "expires_in": 3600}
        assert headers["Authorization"] == "Zoho-oauthtoken tok"
        if url.endswith("/api/accounts"):
            return {"data": [{"accountId": "77", "primaryEmailAddress": "ishit@seleqtwealth.in"}]}
        if method == "POST":
            return {"data": {"messageId": "991"}}
        if "/messages/search" in url:
            return {"data": self.messages}
        if url.endswith("/content"):
            return {"data": {"content": "<div>Yes please.<br>Committee</div>"}}
        raise AssertionError(url)


def zoho_box(http):
    config = mailer.ZohoConfig("id", "secret", "refresh", "ishit@seleqtwealth.in",
                               "https://accounts.zoho.in", "https://mail.zoho.in", "Ishit Lakhani")
    return mailer.ZohoMailbox(config, http=http)


def test_zoho_mailbox_sends_and_catches_replies(client, conn, app):
    import time

    fake = FakeZoho()
    set_mailbox(app, zoho_box(fake))
    tid = task_id(conn, "Gujarati Samaj UAE")
    did = make_draft(client, tid)
    send(client, did)
    assert conn.execute("SELECT message_id FROM outreach WHERE id = ?", (did,)).fetchone()[0] == "zoho:991"
    method, url, payload = fake.calls[-1]
    assert url == "https://mail.zoho.in/api/accounts/77/messages"
    assert payload["toAddress"] == "gujaratisamajemirates@gmail.com" and payload["fromAddress"] == "Ishit Lakhani <ishit@seleqtwealth.in>"
    fake.messages = [{"messageId": "555", "folderId": "1", "subject": "Re: session",
                      "fromAddress": "gujaratisamajemirates@gmail.com", "receivedTime": str(int(time.time() * 1000) + 5000)},
                     {"messageId": "556", "folderId": "1", "subject": "old", "fromAddress": "gujaratisamajemirates@gmail.com",
                      "receivedTime": "1000"}]
    client.post("/mail/check")
    replies = conn.execute("SELECT body, message_id FROM inbound").fetchall()
    assert [(r["body"], r["message_id"]) for r in replies] == [("Yes please.\nCommittee", "zoho:555")]
    rid = make_draft(client, tid, kind="reply")
    client.post(f"/outreach/{rid}", data={"subject": "Re: session", "body": "Thank you.\n\nTest Founder"})
    send(client, rid)
    assert fake.calls[-1][1] == "https://mail.zoho.in/api/accounts/77/messages/555"
    assert fake.calls[-1][2]["action"] == "reply"
    assert sum(1 for c in fake.calls if c[1].endswith("/oauth/v2/token")) == 1  # token reused


def test_open_link_sets_access_and_vercel_path_is_restored(target, tmp_path, monkeypatch):
    import runpy

    app = create_app(target, tmp_path / "none.json", access_key="s3cret-link")
    client = app.test_client()
    assert client.get("/open/wrong").status_code == 404
    resp = client.get("/open/s3cret-link")
    assert resp.status_code == 302 and resp.headers["Location"] == "/"
    assert client.get("/results").status_code == 200
    assert "path seen: /healthz" in client.get("/healthz").get_data(as_text=True)

    monkeypatch.setenv("SELEQT_ACCESS_KEY", "s3cret-link")
    monkeypatch.setenv("DATABASE_URL" if target.startswith("postgres") else "SELEQT_UNUSED", target)
    monkeypatch.chdir(tmp_path)
    entry = runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parent.parent / "api" / "index.py"))
    from werkzeug.test import Client

    vercel = Client(entry["app"])
    resp = vercel.get("/api/index?__path=/open/s3cret-link")
    assert resp.status_code == 302
    resp = vercel.get("/api/index?__path=/calendar")
    assert resp.status_code == 200 and b"Calendar" in resp.data
    resp = vercel.get("/api/index?__path=/healthz&x=1")
    assert b"path seen: /healthz" in resp.data
