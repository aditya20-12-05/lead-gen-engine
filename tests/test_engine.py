import io
import json

import pytest

from engine import create_app, db, drafts, importers, rules, seed, sources

SETTINGS = {"sender_name": "Test Sender", "sender_title": "Wealth Manager", "footer": "SELEQT Private Wealth, Ahmedabad, India"}


@pytest.fixture
def app(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(SETTINGS))
    app = create_app(tmp_path / "engine.db", settings_path)
    app.config["TESTING"] = True
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


def org_id(conn, name):
    return conn.execute("SELECT id FROM organisations WHERE name = ?", (name,)).fetchone()["id"]


def make_draft(client, oid, language="en", kind="invite"):
    resp = client.post(f"/orgs/{oid}/draft", data={"kind": kind, "language": language})
    assert resp.status_code == 302
    return int(resp.headers["Location"].rsplit("/", 1)[1]) if "/outreach/" in resp.headers["Location"] else None


# House style and compliance

def test_house_style_flags_dashes_and_lowercase_brand():
    issues = rules.house_style_issues("Seleqt helps — really – a lot")
    assert any("em dash" in i for i in issues)
    assert any("en dash" in i for i in issues)
    assert any("SELEQT" in i for i in issues)
    assert rules.house_style_issues("SELEQT, (in capitals), with commas") == []


def test_sebi_red_flags():
    assert rules.compliance_issues("Assured returns with no risk")
    assert rules.compliance_issues("Purely educational session") == []


def test_placeholders_block_sending():
    assert rules.placeholder_issues("Dear [Name]") == ["Fill in the placeholder [Name]."]


@pytest.mark.parametrize("key", list(drafts.TEMPLATES))
def test_every_template_passes_copy_checks(key):
    kind, language = key
    org = {"name": "Example Samaj", "kind": kind}
    subject, body = drafts.render_invite(org, language, SETTINGS)
    assert rules.copy_issues(subject + "\n" + body) == []
    assert "SELEQT" in body


# Do not contact

def test_dnc_blocks_drafting_and_cannot_block_webmail(client, conn):
    with pytest.raises(rules.RuleViolation):
        rules.add_dnc(conn, "domain", "gmail.com", "too broad")
    rules.add_dnc(conn, "email", "Gujarati.Samaj.Qatar@gmail.com", "asked not to be contacted")
    oid = org_id(conn, "Gujarati Samaj Qatar")
    assert make_draft(client, oid) is None
    assert conn.execute("SELECT count(*) FROM outreach WHERE org_id = ?", (oid,)).fetchone()[0] == 0


def test_dnc_has_no_delete_route(client):
    assert client.delete("/dnc").status_code == 405


# Nobody contacted twice

def test_one_invite_per_organisation_ever(client, conn):
    oid = org_id(conn, "Gujarati Samaj UAE")
    did = make_draft(client, oid)
    assert client.post(f"/outreach/{did}/sent", data={"sent_by": "Wealth Manager"}).status_code == 302
    assert conn.execute("SELECT sent_at FROM outreach WHERE id = ?", (did,)).fetchone()["sent_at"]
    assert make_draft(client, oid) is None  # second invite blocked


def test_same_email_under_another_name_is_still_blocked(client, conn):
    oid = org_id(conn, "Gujarati Samaj UAE")
    did = make_draft(client, oid)
    client.post(f"/outreach/{did}/sent", data={"sent_by": "WM"})
    conn.execute(
        """INSERT INTO organisations (name, kind, country, contact_email, source_url, created_at)
           VALUES ('GS UAE duplicate', 'community', 'AE', 'gujaratisamajemirates@gmail.com', 'https://x', ?)""",
        (db.now(),),
    )
    conn.commit()
    assert make_draft(client, org_id(conn, "GS UAE duplicate")) is None


def test_reply_only_after_they_write(client, conn):
    oid = org_id(conn, "Gujarati Samaj UAE")
    assert make_draft(client, oid, kind="reply") is None
    did = make_draft(client, oid)
    client.post(f"/outreach/{did}/sent", data={"sent_by": "WM"})
    client.post(f"/orgs/{oid}/inbound", data={"channel": "email", "body": "Yes, please propose a date."})
    rid = make_draft(client, oid, kind="reply")
    assert rid is not None
    # The reply scaffold has a placeholder, so it cannot be marked sent until written.
    client.post(f"/outreach/{rid}/sent", data={"sent_by": "WM"})
    assert conn.execute("SELECT sent_at FROM outreach WHERE id = ?", (rid,)).fetchone()["sent_at"] is None


def test_no_email_means_no_draft(client, conn):
    assert make_draft(client, org_id(conn, "Shri Gujarati Samaj Bahrain")) is None


def test_copy_issues_block_mark_sent(client, conn):
    oid = org_id(conn, "Gujarati Samaj Qatar")
    did = make_draft(client, oid)
    client.post(f"/outreach/{did}", data={"subject": "Guaranteed returns", "body": "Seleqt — hello"})
    client.post(f"/outreach/{did}/sent", data={"sent_by": "WM"})
    assert conn.execute("SELECT sent_at FROM outreach WHERE id = ?", (did,)).fetchone()["sent_at"] is None


def test_gujarati_draft_is_flagged_for_native_review(client, conn):
    did = make_draft(client, org_id(conn, "Gujarati Samaj Qatar"), language="gu")
    assert "native speaker" in client.get(f"/outreach/{did}").get_data(as_text=True)


# Registrations and follow-up

CSV = """name,email,country,consent_followup,consent_text
Asha Example,asha@example.com,GB,yes,I agree to one follow-up email about this session
Ravi Example,ravi@example.com,AE,yes,I agree to one follow-up email about this session
Mina Example,mina@example.com,AU,no,Joining details only
Bad Row,not-an-email,GB,yes,x
"""


def test_import_and_followup_rules(conn):
    conn.execute(
        "INSERT INTO events (title, starts_at, language, cohort, created_at) VALUES ('t', 's', 'English', 'c', ?)",
        (db.now(),),
    )
    rules.add_dnc(conn, "email", "blocked@example.com", "opted out")
    report = importers.import_registrations(
        conn, 1, CSV + "Blocked Person,blocked@example.com,GB,yes,I agree\n"
    )
    assert report == {"added": 3, "duplicate": 0, "do_not_contact": 1, "invalid": [5]}
    regs = {r["email"]: r for r in conn.execute("SELECT * FROM registrations")}
    assert rules.followup_allowed(regs["asha@example.com"])
    assert not rules.followup_allowed(regs["ravi@example.com"])  # Gulf resident
    assert not rules.followup_allowed(regs["mina@example.com"])  # no consent


def test_followup_only_once(client, conn):
    conn.execute(
        "INSERT INTO events (title, starts_at, language, cohort, created_at) VALUES ('t', 's', 'English', 'c', ?)",
        (db.now(),),
    )
    conn.commit()
    importers.import_registrations(conn, 1, CSV)
    rid = conn.execute("SELECT id FROM registrations WHERE email = 'asha@example.com'").fetchone()["id"]
    client.post(f"/registrations/{rid}/followed-up")
    first = conn.execute("SELECT followed_up_at FROM registrations WHERE id = ?", (rid,)).fetchone()[0]
    assert first
    reg = conn.execute("SELECT * FROM registrations WHERE id = ?", (rid,)).fetchone()
    assert not rules.followup_allowed(reg)


# Enquiries

def enquiry(client, **overrides):
    data = {
        "initiated_by_client": "yes", "name": "Kiran Example", "email": "kiran@example.com",
        "country": "GB", "family_key": "example family", "route": "RIA",
        "first_message": "Hello, I attended your session and would like to talk about returning to India.",
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
    enquiry(client, name="Spouse Example", email="spouse@example.com", route="undecided")
    spouse = conn.execute("SELECT id FROM enquiries WHERE name = 'Spouse Example'").fetchone()["id"]
    client.post(f"/enquiries/{spouse}/route", data={"route": "MFD"})
    assert conn.execute("SELECT route FROM enquiries WHERE id = ?", (spouse,)).fetchone()["route"] == "undecided"


# Source health

def test_source_check_records_exact_status(conn):
    statuses = iter(["ok 200", "http 404", "error: timed out", "ok 200", "error: name not resolved"])
    results = sources.check_all(conn, fetch=lambda url: next(statuses))
    assert [s for _, _, s in results] == ["ok 200", "http 404", "error: timed out", "ok 200", "error: name not resolved"]
    stored = [r["source_status"] for r in conn.execute("SELECT source_status FROM organisations ORDER BY id")]
    assert stored == [s for _, _, s in results]


def test_pages_render(client, conn):
    for path in ["/", "/orgs", f"/orgs/{org_id(conn, 'Gujarati Samaj UAE')}", "/events", "/enquiries", "/dnc"]:
        assert client.get(path).status_code == 200, path
