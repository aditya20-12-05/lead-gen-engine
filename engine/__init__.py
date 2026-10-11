"""SELEQT outreach engine: a local web app for the wealth manager's laptop."""

import json
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

from . import db, drafts, importers, rules, sources

COUNTRIES = {
    "AE": "UAE", "QA": "Qatar", "OM": "Oman", "BH": "Bahrain", "KW": "Kuwait", "SA": "Saudi Arabia",
    "GB": "UK", "AU": "Australia", "KE": "Kenya", "TZ": "Tanzania", "UG": "Uganda",
    "ZA": "South Africa", "SG": "Singapore", "US": "USA", "CA": "Canada", "NZ": "New Zealand",
}


def load_settings(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}


def create_app(db_path="data/engine.db", settings_path="data/settings.json"):
    app = Flask(__name__)
    app.config.update(DB_PATH=str(db_path), SETTINGS_PATH=settings_path, SECRET_KEY="local-only")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with db.connect(app.config["DB_PATH"]) as conn:
        db.init(conn)

    def conn():
        if "conn" not in g:
            g.conn = db.connect(app.config["DB_PATH"])
        return g.conn

    @app.teardown_appcontext
    def close(_exc):
        c = g.pop("conn", None)
        if c is not None:
            c.close()

    @app.context_processor
    def globals_():
        return {"countries": COUNTRIES}

    def get_org(org_id):
        org = conn().execute("SELECT * FROM organisations WHERE id = ?", (org_id,)).fetchone()
        if org is None:
            abort(404)
        return org

    @app.get("/")
    def dashboard():
        c = conn()
        orgs = c.execute("SELECT * FROM organisations ORDER BY country, name").fetchall()
        ready, blocked, awaiting = [], [], []
        for org in orgs:
            if rules.awaiting_our_reply(c, org["id"]):
                awaiting.append(org)
                continue
            try:
                rules.check_can_draft(c, org, "invite")
                ready.append(org)
            except rules.RuleViolation as exc:
                if not rules.org_already_invited(c, org["id"], org["contact_email"]):
                    blocked.append((org, str(exc)))
        unsent = c.execute(
            """SELECT o.*, g.name AS org_name FROM outreach o JOIN organisations g ON g.id = o.org_id
               WHERE o.sent_at IS NULL ORDER BY o.drafted_at"""
        ).fetchall()
        unhealthy = [o for o in orgs if not (o["source_status"] or "").startswith("ok")]
        events = c.execute("SELECT * FROM events ORDER BY starts_at").fetchall()
        return render_template(
            "dashboard.html", ready=ready, blocked=blocked, awaiting=awaiting,
            unsent=unsent, unhealthy=unhealthy, events=events,
        )

    @app.route("/orgs", methods=["GET", "POST"])
    def organisations():
        c = conn()
        if request.method == "POST":
            f = request.form
            if not f.get("source_url", "").strip():
                flash("Every organisation needs the source URL its details came from.", "error")
            else:
                c.execute(
                    """INSERT OR IGNORE INTO organisations
                       (name, kind, country, city, contact_email, website, source_url, source_note, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f["name"].strip(), f["kind"], f["country"], f.get("city", "").strip(),
                     rules.normalise_email(f.get("contact_email")) or None,
                     f.get("website", "").strip() or None, f["source_url"].strip(),
                     f.get("source_note", "").strip(), db.now()),
                )
                c.commit()
                flash("Organisation saved.", "ok")
            return redirect(url_for("organisations"))
        orgs = c.execute("SELECT * FROM organisations ORDER BY country, name").fetchall()
        return render_template("organisations.html", orgs=orgs)

    @app.get("/orgs/<int:org_id>")
    def organisation(org_id):
        c = conn()
        org = get_org(org_id)
        history = c.execute(
            """SELECT 'out' AS dir, kind, subject AS summary, coalesce(sent_at, drafted_at) AS at,
                      sent_at, id FROM outreach WHERE org_id = ?
               UNION ALL
               SELECT 'in', channel, body, received_at, received_at, id FROM inbound WHERE org_id = ?
               ORDER BY at""",
            (org_id, org_id),
        ).fetchall()
        return render_template(
            "organisation.html", org=org, history=history,
            templates=drafts.templates_for(org["kind"]),
            dnc=rules.dnc_reason(c, email=org["contact_email"], name=org["name"]),
        )

    @app.post("/orgs/<int:org_id>/edit")
    def edit_organisation(org_id):
        c = conn()
        get_org(org_id)
        f = request.form
        c.execute(
            "UPDATE organisations SET contact_email = ?, website = ?, notes = ? WHERE id = ?",
            (rules.normalise_email(f.get("contact_email")) or None,
             f.get("website", "").strip() or None, f.get("notes", "").strip(), org_id),
        )
        c.commit()
        flash("Saved.", "ok")
        return redirect(url_for("organisation", org_id=org_id))

    @app.post("/orgs/<int:org_id>/draft")
    def draft(org_id):
        c = conn()
        org = get_org(org_id)
        kind = request.form.get("kind", "invite")
        settings = load_settings(app.config["SETTINGS_PATH"])
        try:
            rules.check_can_draft(c, org, kind)
            if kind == "invite":
                language = request.form.get("language", "en")
                subject, body = drafts.render_invite(org, language, settings)
            else:
                language = "en"
                last = c.execute(
                    "SELECT subject FROM outreach WHERE org_id = ? ORDER BY id DESC LIMIT 1", (org_id,)
                ).fetchone()
                subject, body = drafts.render_reply(org, last["subject"] if last else "Your message", settings)
        except (rules.RuleViolation, KeyError) as exc:
            flash(str(exc).strip("'\""), "error")
            return redirect(url_for("organisation", org_id=org_id))
        cur = c.execute(
            """INSERT INTO outreach (org_id, kind, language, subject, body, drafted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (org_id, kind, language, subject, body, db.now()),
        )
        c.commit()
        return redirect(url_for("outreach", outreach_id=cur.lastrowid))

    @app.route("/outreach/<int:outreach_id>", methods=["GET", "POST"])
    def outreach(outreach_id):
        c = conn()
        row = c.execute("SELECT * FROM outreach WHERE id = ?", (outreach_id,)).fetchone()
        if row is None:
            abort(404)
        org = get_org(row["org_id"])
        if request.method == "POST":
            if row["sent_at"]:
                flash("Sent messages cannot be edited.", "error")
            else:
                c.execute(
                    "UPDATE outreach SET subject = ?, body = ? WHERE id = ?",
                    (request.form["subject"], request.form["body"].replace("\r\n", "\n"), outreach_id),
                )
                c.commit()
                flash("Draft saved.", "ok")
            return redirect(url_for("outreach", outreach_id=outreach_id))
        template = drafts.TEMPLATES.get((org["kind"], row["language"]), {})
        return render_template(
            "outreach.html", row=row, org=org,
            issues=rules.copy_issues(row["subject"] + "\n" + row["body"]),
            needs_native_review=template.get("needs_native_review", False) and row["kind"] == "invite",
        )

    @app.post("/outreach/<int:outreach_id>/sent")
    def mark_sent(outreach_id):
        c = conn()
        row = c.execute("SELECT * FROM outreach WHERE id = ?", (outreach_id,)).fetchone()
        if row is None:
            abort(404)
        org = get_org(row["org_id"])
        sent_by = request.form.get("sent_by", "").strip()
        try:
            if not sent_by:
                raise rules.RuleViolation("Record who sent it.")
            rules.check_can_mark_sent(c, row, org)
        except rules.RuleViolation as exc:
            flash(str(exc), "error")
            return redirect(url_for("outreach", outreach_id=outreach_id))
        c.execute("UPDATE outreach SET sent_at = ?, sent_by = ? WHERE id = ?", (db.now(), sent_by, outreach_id))
        c.commit()
        flash("Marked as sent.", "ok")
        return redirect(url_for("organisation", org_id=org["id"]))

    @app.post("/outreach/<int:outreach_id>/discard")
    def discard(outreach_id):
        c = conn()
        row = c.execute("SELECT * FROM outreach WHERE id = ?", (outreach_id,)).fetchone()
        if row is None or row["sent_at"]:
            abort(400)
        c.execute("DELETE FROM outreach WHERE id = ?", (outreach_id,))
        c.commit()
        return redirect(url_for("organisation", org_id=row["org_id"]))

    @app.post("/orgs/<int:org_id>/inbound")
    def log_inbound(org_id):
        c = conn()
        get_org(org_id)
        body = request.form.get("body", "").strip()
        if not body:
            flash("Paste the message you received.", "error")
        else:
            c.execute(
                "INSERT INTO inbound (org_id, received_at, channel, body) VALUES (?, ?, ?, ?)",
                (org_id, db.now(), request.form.get("channel", "email"), body),
            )
            c.commit()
            flash("Message logged.", "ok")
        return redirect(url_for("organisation", org_id=org_id))

    @app.route("/dnc", methods=["GET", "POST"])
    def dnc():
        c = conn()
        if request.method == "POST":
            try:
                rules.add_dnc(c, request.form["kind"], request.form["value"], request.form["reason"])
                flash("Added to the permanent do-not-contact list.", "ok")
            except rules.RuleViolation as exc:
                flash(str(exc), "error")
            return redirect(url_for("dnc"))
        rows = c.execute("SELECT * FROM dnc ORDER BY added_at DESC").fetchall()
        return render_template("dnc.html", rows=rows)

    @app.route("/events", methods=["GET", "POST"])
    def events():
        c = conn()
        if request.method == "POST":
            f = request.form
            c.execute(
                """INSERT INTO events (title, starts_at, language, cohort, host_org_id, platform, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f.get("title") or drafts.WEBINAR_TITLE, f["starts_at"], f["language"], f["cohort"],
                 f.get("host_org_id") or None, f.get("platform", "").strip(), db.now()),
            )
            c.commit()
            return redirect(url_for("events"))
        rows = c.execute(
            """SELECT e.*, g.name AS host_name,
                      (SELECT count(*) FROM registrations r WHERE r.event_id = e.id) AS registered
               FROM events e LEFT JOIN organisations g ON g.id = e.host_org_id ORDER BY starts_at"""
        ).fetchall()
        orgs = c.execute("SELECT id, name FROM organisations ORDER BY name").fetchall()
        return render_template("events.html", rows=rows, orgs=orgs, default_title=drafts.WEBINAR_TITLE)

    @app.route("/events/<int:event_id>", methods=["GET", "POST"])
    def event(event_id):
        c = conn()
        ev = c.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if ev is None:
            abort(404)
        if request.method == "POST":
            upload = request.files.get("csv")
            try:
                if not upload:
                    raise rules.RuleViolation("Choose a CSV file.")
                report = importers.import_registrations(c, event_id, upload.read().decode("utf-8-sig"))
                flash(
                    f"Added {report['added']}, duplicates {report['duplicate']}, "
                    f"do-not-contact skipped {report['do_not_contact']}, "
                    f"invalid rows {report['invalid'] or 'none'}.", "ok",
                )
            except rules.RuleViolation as exc:
                flash(str(exc), "error")
            return redirect(url_for("event", event_id=event_id))
        regs = c.execute("SELECT * FROM registrations WHERE event_id = ? ORDER BY created_at", (event_id,)).fetchall()
        return render_template(
            "event.html", ev=ev, regs=regs, followup={r["id"]: rules.followup_allowed(r) for r in regs},
        )

    @app.post("/registrations/<int:reg_id>/followed-up")
    def followed_up(reg_id):
        c = conn()
        reg = c.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
        if reg is None:
            abort(404)
        if not rules.followup_allowed(reg) or rules.dnc_reason(c, email=reg["email"], name=reg["name"]):
            flash("Follow-up not allowed for this registration.", "error")
        else:
            c.execute("UPDATE registrations SET followed_up_at = ? WHERE id = ?", (db.now(), reg_id))
            c.commit()
        return redirect(url_for("event", event_id=reg["event_id"]))

    @app.route("/enquiries", methods=["GET", "POST"])
    def enquiries():
        c = conn()
        if request.method == "POST":
            f = request.form
            try:
                if f.get("initiated_by_client") != "yes":
                    raise rules.RuleViolation(
                        "Only log people who contacted SELEQT first; record their first message as evidence."
                    )
                if not f.get("first_message", "").strip():
                    raise rules.RuleViolation("Paste their first message, word for word.")
                reason = rules.dnc_reason(c, email=f.get("email"), name=f.get("name"), phone=f.get("phone"))
                if reason:
                    raise rules.RuleViolation(f"On the do-not-contact list ({reason}).")
                family_key = (f.get("family_key") or f.get("email") or f["name"]).strip().lower()
                rules.check_route(c, None, family_key, f.get("route", "undecided"))
                c.execute(
                    """INSERT INTO enquiries
                       (name, email, phone, country, citizenship, oci, family_key, route,
                        first_contact_at, first_contact_channel, first_message, ticket_fit,
                        source_event_id, source_org_id, notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f["name"].strip(), rules.normalise_email(f.get("email")) or None,
                     f.get("phone", "").strip() or None, f["country"], f.get("citizenship", "").strip(),
                     1 if f.get("oci") == "yes" else 0 if f.get("oci") == "no" else None,
                     family_key, f.get("route", "undecided"), f.get("first_contact_at") or db.now(),
                     f.get("first_contact_channel", "email"), f["first_message"].strip(),
                     f.get("ticket_fit", "unknown"), f.get("source_event_id") or None,
                     f.get("source_org_id") or None, f.get("notes", "").strip(), db.now()),
                )
                c.commit()
                flash("Enquiry logged.", "ok")
            except rules.RuleViolation as exc:
                flash(str(exc), "error")
            return redirect(url_for("enquiries"))
        rows = c.execute("SELECT * FROM enquiries ORDER BY first_contact_at DESC").fetchall()
        orgs = c.execute("SELECT id, name FROM organisations ORDER BY name").fetchall()
        evs = c.execute("SELECT id, title, starts_at FROM events ORDER BY starts_at").fetchall()
        return render_template("enquiries.html", rows=rows, orgs=orgs, evs=evs)

    @app.post("/enquiries/<int:enquiry_id>/route")
    def set_route(enquiry_id):
        c = conn()
        enq = c.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
        if enq is None:
            abort(404)
        route = request.form["route"]
        try:
            rules.check_route(c, enquiry_id, enq["family_key"], route)
            c.execute("UPDATE enquiries SET route = ? WHERE id = ?", (route, enquiry_id))
            c.commit()
        except rules.RuleViolation as exc:
            flash(str(exc), "error")
        return redirect(url_for("enquiries"))

    @app.post("/sources/check")
    def check_sources():
        results = sources.check_all(conn())
        ok = sum(1 for _, _, s in results if s.startswith("ok"))
        flash(f"Checked {len(results)} sources: {ok} reachable, {len(results) - ok} not.", "ok")
        return redirect(url_for("organisations"))

    return app
