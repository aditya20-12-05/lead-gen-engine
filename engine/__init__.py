"""SELEQT outreach engine: a local web app for the founder's laptop.

Structure: country > approach (a channel with SELEQT's brief) > task (one
organisation, its brief, the plan and the email thread).
"""

import json
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

from . import db, drafts, importers, mailer, rules, sources

COUNTRIES = {
    "AE": "UAE", "QA": "Qatar", "OM": "Oman", "BH": "Bahrain", "KW": "Kuwait", "SA": "Saudi Arabia",
    "GB": "UK", "AU": "Australia", "KE": "Kenya", "TZ": "Tanzania", "UG": "Uganda",
    "ZA": "South Africa", "SG": "Singapore", "US": "USA", "CA": "Canada", "NZ": "New Zealand",
}


def load_settings(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}


def task_status(c, org):
    """Where a task stands, derived from the guardrails and the email thread."""
    if rules.dnc_reason(c, email=org["contact_email"], name=org["name"], phone=org["contact_phone"]):
        return "do not contact"
    if rules.awaiting_our_reply(c, org["id"]):
        return "reply waiting"
    if c.execute("SELECT 1 FROM outreach WHERE org_id = ? AND sent_at IS NOT NULL", (org["id"],)).fetchone():
        return "sent, awaiting reply"
    if c.execute("SELECT 1 FROM outreach WHERE org_id = ? AND sent_at IS NULL", (org["id"],)).fetchone():
        return "draft"
    if not rules.available_channels(org):
        return "needs contact"
    return "ready"


def create_app(db_path="data/engine.db", settings_path="data/settings.json"):
    app = Flask(__name__)
    app.config.update(
        DB_PATH=str(db_path),
        SETTINGS_PATH=settings_path,
        SECRET_KEY="local-only",
        MAIL_CONFIG=lambda settings: mailer.MailConfig.from_env(settings.get("sender_name", "")),
        MAIL_SEND=mailer.send,
        MAIL_FETCH=mailer.fetch_replies,
    )
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with db.connect(app.config["DB_PATH"]) as conn:
        db.init(conn)

    def conn():
        if "conn" not in g:
            g.conn = db.connect(app.config["DB_PATH"])
        return g.conn

    def settings():
        return load_settings(app.config["SETTINGS_PATH"])

    def mail_config():
        return app.config["MAIL_CONFIG"](settings())

    @app.teardown_appcontext
    def close(_exc):
        c = g.pop("conn", None)
        if c is not None:
            c.close()

    @app.context_processor
    def globals_():
        config = mail_config()
        return {"countries": COUNTRIES, "mail_user": config.user if config else None, "channels": rules.CHANNELS}

    def one(sql, args):
        row = conn().execute(sql, args).fetchone()
        if row is None:
            abort(404)
        return row

    def get_org(org_id):
        return one("SELECT * FROM organisations WHERE id = ?", (org_id,))

    def get_task(task_id):
        return one(
            """SELECT t.*, a.name AS approach_name, a.country, a.our_brief, a.template_kind, a.status AS approach_status
               FROM tasks t JOIN approaches a ON a.id = t.approach_id WHERE t.id = ?""",
            (task_id,),
        )

    def tasks_for(where, args):
        c = conn()
        rows = c.execute(
            f"""SELECT t.id, t.owner, a.id AS approach_id, a.name AS approach_name, a.country, g.*
                FROM tasks t JOIN approaches a ON a.id = t.approach_id JOIN organisations g ON g.id = t.org_id
                WHERE {where} ORDER BY g.name""",
            args,
        ).fetchall()
        return [{"task_id": r["id"], "owner": r["owner"], "org": r, "status": task_status(c, r)} for r in rows]

    # Overview, countries, approaches, tasks

    @app.get("/")
    def overview():
        c = conn()
        summary = {}
        for a in c.execute("SELECT * FROM approaches ORDER BY country, name"):
            tasks = tasks_for("t.approach_id = ?", (a["id"],))
            entry = summary.setdefault(a["country"], {"approaches": [], "waiting": 0})
            entry["approaches"].append({"approach": a, "count": len(tasks),
                                        "ready": sum(t["status"] == "ready" for t in tasks)})
            entry["waiting"] += sum(t["status"] == "reply waiting" for t in tasks)
        waiting = [t for t in tasks_for("1 = 1", ()) if t["status"] == "reply waiting"]
        events = c.execute("SELECT * FROM events ORDER BY starts_at").fetchall()
        return render_template("overview.html", summary=summary, waiting=waiting, events=events)

    @app.route("/countries/<code>", methods=["GET", "POST"])
    def country(code):
        c = conn()
        if code not in COUNTRIES:
            abort(404)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            brief = request.form.get("our_brief", "").strip()
            if not name or not brief:
                flash("An approach needs a name and our brief.", "error")
            else:
                c.execute(
                    """INSERT OR IGNORE INTO approaches (country, name, our_brief, template_kind, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (code, name, brief, request.form.get("template_kind") or None,
                     request.form.get("status", "active"), db.now()),
                )
                c.commit()
            return redirect(url_for("country", code=code))
        approaches = [
            {"approach": a, "tasks": tasks_for("t.approach_id = ?", (a["id"],))}
            for a in c.execute("SELECT * FROM approaches WHERE country = ? ORDER BY name", (code,))
        ]
        return render_template("country.html", code=code, approaches=approaches)

    @app.route("/approaches/<int:approach_id>", methods=["GET", "POST"])
    def approach(approach_id):
        c = conn()
        a = one("SELECT * FROM approaches WHERE id = ?", (approach_id,))
        if request.method == "POST":
            action = request.form.get("action")
            if action == "brief":
                c.execute(
                    "UPDATE approaches SET our_brief = ?, status = ? WHERE id = ?",
                    (request.form["our_brief"].strip(), request.form["status"], approach_id),
                )
                flash("Brief saved.", "ok")
            elif action == "add_task":
                org_id = request.form.get("org_id")
                if not org_id:
                    if not request.form.get("source_url", "").strip() or not request.form.get("name", "").strip():
                        flash("A new organisation needs a name and the source URL its details came from.", "error")
                        return redirect(url_for("approach", approach_id=approach_id))
                    c.execute(
                        """INSERT OR IGNORE INTO organisations
                           (name, kind, country, city, contact_email, contact_phone, contact_form_url, social_url,
                            website, source_url, source_note, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (request.form["name"].strip(), request.form["kind"], a["country"],
                         request.form.get("city", "").strip(),
                         rules.normalise_email(request.form.get("contact_email")) or None,
                         request.form.get("contact_phone", "").strip() or None,
                         request.form.get("contact_form_url", "").strip() or None,
                         request.form.get("social_url", "").strip() or None,
                         request.form.get("website", "").strip() or None, request.form["source_url"].strip(),
                         request.form.get("source_note", "").strip(), db.now()),
                    )
                    org_id = c.execute(
                        "SELECT id FROM organisations WHERE name = ? AND country = ?",
                        (request.form["name"].strip(), a["country"]),
                    ).fetchone()["id"]
                c.execute(
                    "INSERT OR IGNORE INTO tasks (approach_id, org_id, created_at) VALUES (?, ?, ?)",
                    (approach_id, org_id, db.now()),
                )
                flash("Task added.", "ok")
            c.commit()
            return redirect(url_for("approach", approach_id=approach_id))
        tasks = tasks_for("t.approach_id = ?", (approach_id,))
        in_task = {t["org"]["id"] for t in tasks}
        candidates = [o for o in c.execute(
            "SELECT id, name FROM organisations WHERE country = ? ORDER BY name", (a["country"],)
        ) if o["id"] not in in_task]
        return render_template("approach.html", a=a, tasks=tasks, candidates=candidates)

    @app.route("/tasks/<int:task_id>", methods=["GET", "POST"])
    def task(task_id):
        c = conn()
        t = get_task(task_id)
        org = get_org(t["org_id"])
        if request.method == "POST":
            c.execute(
                "UPDATE tasks SET plan = ?, owner = ? WHERE id = ?",
                (request.form.get("plan", "").strip(), request.form.get("owner", "").strip(), task_id),
            )
            c.execute(
                """UPDATE organisations SET contact_email = ?, contact_phone = ?, contact_form_url = ?,
                   social_url = ?, source_note = ? WHERE id = ?""",
                (rules.normalise_email(request.form.get("contact_email")) or None,
                 request.form.get("contact_phone", "").strip() or None,
                 request.form.get("contact_form_url", "").strip() or None,
                 request.form.get("social_url", "").strip() or None,
                 request.form.get("source_note", "").strip(), org["id"]),
            )
            c.commit()
            flash("Saved.", "ok")
            return redirect(url_for("task", task_id=task_id))
        thread = c.execute(
            """SELECT 'out' AS dir, id, kind, channel, subject, body, coalesce(sent_at, drafted_at) AS at,
                      sent_at, sent_by FROM outreach WHERE org_id = ?
               UNION ALL
               SELECT 'in', id, 'reply', channel, coalesce(subject, ''), body, received_at, received_at, from_addr
               FROM inbound WHERE org_id = ? ORDER BY at""",
            (org["id"], org["id"]),
        ).fetchall()
        return render_template(
            "task.html", t=t, org=org, thread=thread, status=task_status(c, org),
            usable=rules.available_channels(org),
            templates=drafts.templates_for(t["template_kind"]) if t["template_kind"] else {},
        )

    @app.post("/tasks/<int:task_id>/draft")
    def draft(task_id):
        c = conn()
        t = get_task(task_id)
        org = get_org(t["org_id"])
        kind = request.form.get("kind", "invite")
        channel = request.form.get("channel", "email")
        try:
            rules.check_can_draft(c, org, kind, channel)
            language = request.form.get("language", "en")
            if kind == "reply":
                last = c.execute(
                    "SELECT subject FROM inbound WHERE org_id = ? ORDER BY received_at DESC LIMIT 1", (org["id"],)
                ).fetchone()
                subject, body = drafts.render_reply(org, (last and last["subject"]) or "Your message", settings())
            elif request.form.get("template") == "blank" or not t["template_kind"]:
                subject, body = drafts.render_blank(settings())
            else:
                subject, body = drafts.render_invite({**dict(org), "kind": t["template_kind"]}, language, settings())
        except (rules.RuleViolation, KeyError) as exc:
            flash(str(exc).strip("'\""), "error")
            return redirect(url_for("task", task_id=task_id))
        cur = c.execute(
            """INSERT INTO outreach (org_id, task_id, kind, channel, language, subject, body, drafted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (org["id"], task_id, kind, channel, language, subject, body, db.now()),
        )
        c.commit()
        return redirect(url_for("outreach", outreach_id=cur.lastrowid))

    @app.route("/outreach/<int:outreach_id>", methods=["GET", "POST"])
    def outreach(outreach_id):
        c = conn()
        row = one("SELECT * FROM outreach WHERE id = ?", (outreach_id,))
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
        task_kind = None
        if row["task_id"]:
            task_kind = get_task(row["task_id"])["template_kind"]
        template = drafts.TEMPLATES.get((task_kind, row["language"]), {})
        return render_template(
            "outreach.html", row=row, org=org,
            issues=rules.copy_issues(row["subject"] + "\n" + row["body"]),
            needs_native_review=template.get("needs_native_review", False) and row["kind"] == "invite",
        )

    def back_to(row):
        return redirect(url_for("task", task_id=row["task_id"]) if row["task_id"]
                        else url_for("organisation", org_id=row["org_id"]))

    @app.post("/outreach/<int:outreach_id>/send")
    def send(outreach_id):
        c = conn()
        row = one("SELECT * FROM outreach WHERE id = ?", (outreach_id,))
        org = get_org(row["org_id"])
        config = mail_config()
        try:
            if row["channel"] != "email":
                raise rules.RuleViolation("Only emails can be sent from the engine; record other channels as sent.")
            if config is None:
                raise rules.RuleViolation("The mailbox is not connected.")
            if request.form.get("reviewed") != "yes":
                raise rules.RuleViolation("Tick the box to confirm you have read the email before sending.")
            if not row["subject"].strip():
                raise rules.RuleViolation("Add a subject.")
            rules.check_can_mark_sent(c, row, org)
            in_reply_to = None
            if row["kind"] == "reply":
                last = c.execute(
                    "SELECT message_id FROM inbound WHERE org_id = ? AND message_id IS NOT NULL "
                    "ORDER BY received_at DESC LIMIT 1", (org["id"],)
                ).fetchone()
                in_reply_to = last["message_id"] if last else None
            msg = mailer.build_message(config, org["contact_email"], row["subject"], row["body"], in_reply_to)
            message_id = app.config["MAIL_SEND"](config, msg)
        except rules.RuleViolation as exc:
            flash(str(exc), "error")
            return redirect(url_for("outreach", outreach_id=outreach_id))
        except Exception as exc:  # network or login failure: nothing is marked sent
            flash(f"Not sent: {exc}", "error")
            return redirect(url_for("outreach", outreach_id=outreach_id))
        c.execute(
            "UPDATE outreach SET sent_at = ?, sent_by = ?, message_id = ? WHERE id = ?",
            (db.now(), config.user, message_id, outreach_id),
        )
        c.commit()
        flash(f"Sent from {config.user}.", "ok")
        return back_to(row)

    @app.post("/outreach/<int:outreach_id>/sent")
    def mark_sent(outreach_id):
        """For an email sent personally from the mailbox rather than from the engine."""
        c = conn()
        row = one("SELECT * FROM outreach WHERE id = ?", (outreach_id,))
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
        return back_to(row)

    @app.post("/outreach/<int:outreach_id>/discard")
    def discard(outreach_id):
        c = conn()
        row = one("SELECT * FROM outreach WHERE id = ?", (outreach_id,))
        if row["sent_at"]:
            abort(400)
        c.execute("DELETE FROM outreach WHERE id = ?", (outreach_id,))
        c.commit()
        return back_to(row)

    @app.post("/mail/check")
    def check_mail():
        config = mail_config()
        if config is None:
            flash("The mailbox is not connected.", "error")
        else:
            try:
                result = app.config["MAIL_FETCH"](conn(), config)
                message = f"{result['new']} new repl{'y' if result['new'] == 1 else 'ies'}."
                if result["opt_outs"]:
                    message += " Added to do not contact: " + ", ".join(result["opt_outs"]) + "."
                flash(message, "ok")
            except Exception as exc:
                flash(f"Could not check the mailbox: {exc}", "error")
        return redirect(request.form.get("next") or url_for("overview"))

    @app.post("/orgs/<int:org_id>/inbound")
    def log_inbound(org_id):
        """For replies that arrive by phone, WhatsApp or another inbox."""
        c = conn()
        get_org(org_id)
        body = request.form.get("body", "").strip()
        if not body:
            flash("Paste the message you received.", "error")
        else:
            c.execute(
                "INSERT INTO inbound (org_id, task_id, received_at, channel, body) VALUES (?, ?, ?, ?, ?)",
                (org_id, request.form.get("task_id") or None, db.now(), request.form.get("channel", "email"), body),
            )
            c.commit()
            flash("Message logged.", "ok")
        return redirect(request.form.get("next") or url_for("organisation", org_id=org_id))

    # Organisations

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
                       (name, kind, country, city, contact_email, contact_phone, contact_form_url, social_url,
                        website, source_url, source_note, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f["name"].strip(), f["kind"], f["country"], f.get("city", "").strip(),
                     rules.normalise_email(f.get("contact_email")) or None,
                     f.get("contact_phone", "").strip() or None, f.get("contact_form_url", "").strip() or None,
                     f.get("social_url", "").strip() or None,
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
        tasks = tasks_for("t.org_id = ?", (org_id,))
        return render_template(
            "organisation.html", org=org, tasks=tasks,
            dnc=rules.dnc_reason(c, email=org["contact_email"], name=org["name"]),
        )

    @app.post("/orgs/<int:org_id>/edit")
    def edit_organisation(org_id):
        c = conn()
        get_org(org_id)
        f = request.form
        c.execute(
            """UPDATE organisations SET contact_email = ?, contact_phone = ?, contact_form_url = ?, social_url = ?,
               website = ?, source_note = ?, notes = ? WHERE id = ?""",
            (rules.normalise_email(f.get("contact_email")) or None, f.get("contact_phone", "").strip() or None,
             f.get("contact_form_url", "").strip() or None, f.get("social_url", "").strip() or None,
             f.get("website", "").strip() or None,
             f.get("source_note", "").strip(), f.get("notes", "").strip(), org_id),
        )
        c.commit()
        flash("Saved.", "ok")
        return redirect(url_for("organisation", org_id=org_id))

    @app.post("/sources/check")
    def check_sources():
        results = sources.check_all(conn())
        ok = sum(1 for _, _, s in results if s.startswith("ok"))
        flash(f"Checked {len(results)} sources: {ok} reachable, {len(results) - ok} not.", "ok")
        return redirect(url_for("organisations"))

    # Do not contact

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

    # Webinars and registrations

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
        ev = one("SELECT * FROM events WHERE id = ?", (event_id,))
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
        reg = one("SELECT * FROM registrations WHERE id = ?", (reg_id,))
        if not rules.followup_allowed(reg) or rules.dnc_reason(c, email=reg["email"], name=reg["name"]):
            flash("Follow-up not allowed for this registration.", "error")
        else:
            c.execute("UPDATE registrations SET followed_up_at = ? WHERE id = ?", (db.now(), reg_id))
            c.commit()
        return redirect(url_for("event", event_id=reg["event_id"]))

    # Enquiries

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
        enq = one("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,))
        route = request.form["route"]
        try:
            rules.check_route(c, enquiry_id, enq["family_key"], route)
            c.execute("UPDATE enquiries SET route = ? WHERE id = ?", (route, enquiry_id))
            c.commit()
        except rules.RuleViolation as exc:
            flash(str(exc), "error")
        return redirect(url_for("enquiries"))

    return app
