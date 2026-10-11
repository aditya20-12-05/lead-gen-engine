"""SELEQT outreach engine.

Structure: country > approach (a channel with SELEQT's brief) > task (one
organisation, its brief, the plan and the email thread).
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import threading
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for
from markupsafe import escape

from . import db, drafts, finder, importers, mailer, rules, seed, sources

ACCESS_COOKIE = "seleqt_access"

COUNTRIES = {
    "AE": "UAE", "QA": "Qatar", "OM": "Oman", "BH": "Bahrain", "KW": "Kuwait", "SA": "Saudi Arabia",
    "GB": "UK", "AU": "Australia", "KE": "Kenya", "TZ": "Tanzania", "UG": "Uganda",
    "ZA": "South Africa", "SG": "Singapore", "US": "USA", "CA": "Canada", "NZ": "New Zealand",
}


def load_settings(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}


def status_context(c):
    """Everything task statuses depend on, in five queries instead of several per task."""
    return {
        "dnc": {(r["kind"], r["value"]) for r in c.execute("SELECT kind, value FROM dnc")},
        "last_out": {r["org_id"]: r["t"] for r in c.execute(
            "SELECT org_id, max(sent_at) AS t FROM outreach WHERE sent_at IS NOT NULL GROUP BY org_id")},
        "last_in": {r["org_id"]: r["t"] for r in c.execute(
            "SELECT org_id, max(received_at) AS t FROM inbound GROUP BY org_id")},
        "drafts": {r["org_id"] for r in c.execute(
            "SELECT DISTINCT org_id FROM outreach WHERE sent_at IS NULL")},
    }


def task_status(c, org, ctx=None):
    """Where a task stands, derived from the guardrails and the email thread."""
    ctx = ctx or status_context(c)
    keys = rules.dnc_keys(org["contact_email"], org["name"], org["contact_phone"])
    if any(key in ctx["dnc"] for key in keys):
        return "do not contact"
    last_in, last_out = ctx["last_in"].get(org["id"]), ctx["last_out"].get(org["id"])
    if last_in and (last_out is None or last_in > last_out):
        return "reply waiting"
    if last_out:
        return "sent, awaiting reply"
    if org["id"] in ctx["drafts"]:
        return "draft"
    if not rules.available_channels(org):
        return "needs contact"
    return "ready"


def create_app(db_path=None, settings_path="data/settings.json", access_key=None):
    """Hosted, it reads DATABASE_URL, SELEQT_ACCESS_KEY and SELEQT_SECRET_KEY from the environment."""
    app = Flask(__name__)
    # DATABASE_URL (Neon) or POSTGRES_URL (Vercel's Supabase integration) when hosted.
    target = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or db_path or "data/engine.db"
    app.config.update(
        DB_PATH=str(target),
        SETTINGS_PATH=settings_path,
        SECRET_KEY=os.environ.get("SELEQT_SECRET_KEY") or secrets.token_hex(32),
        # Tolerate quotes or backticks pasted around the value in a hosting dashboard.
        ACCESS_KEY=(access_key if access_key is not None
                    else os.environ.get("SELEQT_ACCESS_KEY", "")).strip().strip("'\"`").strip() or None,
        MAILBOX=lambda settings: mailer.mailbox_from_env(settings.get("sender_name", drafts.DEFAULT_SETTINGS["sender_name"])),
        FETCH_PAGE=finder.fetch_page,
    )
    try:
        if os.environ.get("VERCEL") and not db.is_postgres_url(target):
            raise RuntimeError("DATABASE_URL is missing or is not a Postgres link (it should start with postgresql://). Fix it in Vercel and redeploy.")
        if not db.is_postgres_url(target):
            Path(target).parent.mkdir(parents=True, exist_ok=True)
        with db.connect(app.config["DB_PATH"]) as conn:
            db.init(conn)
            if conn.execute("SELECT count(*) FROM approaches").fetchone()[0] == 0:
                seed.seed(conn)  # first start on a new database
            seed.apply_contact_updates(conn)
    except Exception as exc:  # show what went wrong rather than crashing the function
        message = f"{type(exc).__name__}: {exc}"
        if db.is_postgres_url(target):
            message = db.redact(message, target)

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def startup_error(path):
            key = app.config["ACCESS_KEY"]
            opened = request.path[len("/open/"):].strip("/") if request.path.startswith("/open/") else ""
            given = (opened or request.args.get("key") or request.cookies.get(ACCESS_COOKIE, "")).strip()
            if key and not hmac.compare_digest(given, key):
                abort(404)  # details only through the secret link
            return (f"<h1>SELEQT outreach could not start</h1><p>{escape(message)}</p>", 500)

        return app

    @app.before_request
    def secret_link():
        """With an access key set, only the secret link (or its cookie) opens the app."""
        key = app.config["ACCESS_KEY"]
        if not key or request.path == "/healthz":
            return None
        if request.path.startswith("/open/"):
            given = request.path[len("/open/"):].strip("/")
            if hmac.compare_digest(given.strip(), key):
                response = redirect("/")
                response.set_cookie(ACCESS_COOKIE, key, max_age=400 * 24 * 3600, httponly=True,
                                    secure=request.is_secure, samesite="Lax")
                return response
            abort(404)
        given = request.args.get("key")
        if given is not None and hmac.compare_digest(given.strip(), key):
            args = {k: v for k, v in request.args.items() if k != "key"}
            response = redirect(url_for(request.endpoint, **(request.view_args or {}), **args)
                                if request.endpoint else "/")
            response.set_cookie(ACCESS_COOKIE, key, max_age=400 * 24 * 3600, httponly=True,
                                secure=request.is_secure, samesite="Lax")
            return response
        if hmac.compare_digest(request.cookies.get(ACCESS_COOKIE, ""), key):
            return None
        abort(404)

    @app.after_request
    def no_index(response):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.get("/healthz")
    def healthz():
        # Safe to show: no secrets, only whether they are set.
        key = app.config["ACCESS_KEY"]
        fingerprint = hashlib.sha256(key.encode()).hexdigest()[:8] if key else "none"
        return (f"ok | access key set: {'yes' if key else 'no'} (fingerprint {fingerprint}, {len(key or '')} characters)"
                f" | database: {'postgres' if db.is_postgres_url(app.config['DB_PATH']) else 'sqlite'}"
                f" | path seen: {request.path}"
                f" | code version: {os.environ.get('VERCEL_GIT_COMMIT_SHA', 'local')[:7]}"), 200, {"Content-Type": "text/plain"}

    shared = threading.local()

    def conn():
        """Postgres: one connection per worker thread, reused across requests (saves the
        connection handshake on every page). SQLite: a fresh connection per request."""
        if "conn" not in g:
            if db.is_postgres_url(app.config["DB_PATH"]):
                existing = getattr(shared, "conn", None)
                if existing is None or existing.closed:
                    shared.conn = db.connect(app.config["DB_PATH"])
                g.conn = shared.conn
            else:
                g.conn = db.connect(app.config["DB_PATH"])
        return g.conn

    def settings():
        return load_settings(app.config["SETTINGS_PATH"])

    def mailbox():
        if "mailbox" not in app.extensions:
            app.extensions["mailbox"] = app.config["MAILBOX"](settings())
        return app.extensions["mailbox"]

    @app.teardown_appcontext
    def close(_exc):
        c = g.pop("conn", None)
        if c is None:
            return
        if getattr(c, "is_postgres", False):
            c.rollback()  # end any open transaction; keep the connection for the next request
        else:
            c.close()

    @app.context_processor
    def globals_():
        box = mailbox()
        return {"countries": COUNTRIES, "mail_user": box.user if box else None, "channels": rules.CHANNELS,
                "today": date.today().isoformat()}

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
            f"""SELECT g.*, t.id AS task_id, t.owner AS task_owner, t.outcome AS task_outcome,
                       t.next_action AS task_next_action, t.next_action_date AS task_next_action_date,
                       a.id AS approach_id, a.name AS approach_name
                FROM tasks t JOIN approaches a ON a.id = t.approach_id JOIN organisations g ON g.id = t.org_id
                WHERE {where} ORDER BY g.name""",
            args,
        ).fetchall()
        ctx = status_context(c) if rows else None
        return [{"task_id": r["task_id"], "owner": r["task_owner"], "outcome": r["task_outcome"],
                 "next_action": r["task_next_action"], "next_action_date": r["task_next_action_date"],
                 "approach_id": r["approach_id"], "approach_name": r["approach_name"],
                 "org": r, "status": task_status(c, r, ctx)} for r in rows]

    # Overview, countries, approaches, tasks

    @app.get("/")
    def overview():
        auto_check_mail()
        c = conn()
        summary = {}
        all_tasks = tasks_for("1 = 1", ())
        for a in c.execute("SELECT * FROM approaches ORDER BY country, name").fetchall():
            tasks = [t for t in all_tasks if t["approach_id"] == a["id"]]
            entry = summary.setdefault(a["country"], {"approaches": [], "waiting": 0})
            entry["approaches"].append({"approach": a, "count": len(tasks),
                                        "ready": sum(t["status"] == "ready" for t in tasks)})
            entry["waiting"] += sum(t["status"] == "reply waiting" for t in tasks)
        waiting = [t for t in all_tasks if t["status"] == "reply waiting"]
        today = date.today()
        soon = [i for i in agenda("0000-01-01", (today + timedelta(days=7)).isoformat())
                if not i["done"] and (i["kind"] == "task" or (i["end_date"] or i["date"]) >= today.isoformat())]
        return render_template("overview.html", summary=summary, waiting=waiting, soon=soon)

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
                        flash("A new organisation needs a name and where its details came from.", "error")
                        return redirect(url_for("country", code=a["country"]) + f"#approach-{approach_id}")
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
                flash("Added.", "ok")
            c.commit()
            return redirect(url_for("country", code=a["country"]) + f"#approach-{approach_id}")
        return redirect(url_for("country", code=a["country"]) + f"#approach-{approach_id}")

    def current_draft(org_id):
        return conn().execute(
            "SELECT * FROM outreach WHERE org_id = ? AND sent_at IS NULL AND channel = 'email' "
            "ORDER BY id DESC LIMIT 1", (org_id,)
        ).fetchone()

    @app.route("/tasks/<int:task_id>", methods=["GET", "POST"])
    def task(task_id):
        c = conn()
        t = get_task(task_id)
        org = get_org(t["org_id"])
        if request.method == "POST":
            f = request.form
            c.execute("UPDATE tasks SET plan = ? WHERE id = ?", (f.get("plan", t["plan"] or "").strip(), task_id))
            if "outcome" in f and f["outcome"] in ("open", "agreed", "live", "declined"):
                c.execute(
                    "UPDATE tasks SET owner = ?, outcome = ?, next_action = ?, next_action_date = ? WHERE id = ?",
                    (f.get("owner", "").strip(), f["outcome"], f.get("next_action", "").strip() or None,
                     f.get("next_action_date", "").strip() or None, task_id),
                )
            c.execute(
                """UPDATE organisations SET contact_email = ?, contact_phone = ?, contact_form_url = ?,
                   social_url = ?, source_note = ? WHERE id = ?""",
                (rules.normalise_email(f.get("contact_email")) or None,
                 f.get("contact_phone", org["contact_phone"] or "").strip() or None,
                 f.get("contact_form_url", org["contact_form_url"] or "").strip() or None,
                 f.get("social_url", org["social_url"] or "").strip() or None,
                 f.get("source_note", "").strip(), org["id"]),
            )
            c.commit()
            flash("Saved.", "ok")
            return redirect(url_for("task", task_id=task_id))
        auto_check_mail()
        thread = c.execute(
            """SELECT 'out' AS dir, id, kind, channel, subject, body, sent_at AS at, sent_at, sent_by
               FROM outreach WHERE org_id = ? AND sent_at IS NOT NULL
               UNION ALL
               SELECT 'in', id, 'reply', channel, coalesce(subject, ''), body, received_at, received_at, from_addr
               FROM inbound WHERE org_id = ? ORDER BY at""",
            (org["id"], org["id"]),
        ).fetchall()
        status = task_status(c, org)
        draft_row = current_draft(org["id"])
        return render_template(
            "task.html", t=t, org=org, thread=thread, status=status, draft=draft_row,
            issues=rules.copy_issues(draft_row["subject"] + "\n" + draft_row["body"]) if draft_row else [],
            usable=[ch for ch in rules.available_channels(org) if ch != "email"],
            templates=drafts.templates_for(t["template_kind"]) if t["template_kind"] else {},
        )

    @app.post("/tasks/<int:task_id>/compose")
    def compose(task_id):
        """Write, fill from template, save or send the email for this task, all on the task page."""
        c = conn()
        t = get_task(task_id)
        org = get_org(t["org_id"])
        action = request.form.get("action", "save")
        kind = "reply" if task_status(c, org) == "reply waiting" else "invite"
        existing = current_draft(org["id"])
        try:
            rules.check_can_draft(c, org, existing["kind"] if existing else kind, "email")
        except rules.RuleViolation as exc:
            flash(str(exc), "error")
            return redirect(url_for("task", task_id=task_id))
        subject = request.form.get("subject", existing["subject"] if existing else "")
        body = request.form.get("body", existing["body"] if existing else "").replace("\r\n", "\n")
        language = request.form.get("language", "en")
        if action == "template" and t["template_kind"]:
            subject, body = drafts.render_invite({**dict(org), "kind": t["template_kind"]}, language, settings())
        elif action == "start" and not existing:
            subject, body = (drafts.render_reply(org, "Your message", settings()) if kind == "reply"
                             else drafts.render_blank(settings()))
        if existing:
            c.execute("UPDATE outreach SET subject = ?, body = ? WHERE id = ?", (subject, body, existing["id"]))
            draft_id = existing["id"]
        else:
            draft_id = c.execute(
                """INSERT INTO outreach (org_id, task_id, kind, channel, language, subject, body, drafted_at)
                   VALUES (?, ?, ?, 'email', ?, ?, ?, ?)""",
                (org["id"], task_id, kind, language, subject, body, db.now()),
            ).lastrowid
        c.commit()
        if action == "send":
            row = one("SELECT * FROM outreach WHERE id = ?", (draft_id,))
            error = deliver(row, org, request.form.get("reviewed") == "yes")
            flash(error or f"Sent from {mailbox().user}.", "error" if error else "ok")
        elif action == "discard":
            c.execute("DELETE FROM outreach WHERE id = ? AND sent_at IS NULL", (draft_id,))
            c.commit()
        elif action == "save":
            flash("Draft saved.", "ok")
        return redirect(url_for("task", task_id=task_id) + "#email")

    @app.post("/tasks/<int:task_id>/contacted")
    def contacted(task_id):
        """Record contact made outside email (WhatsApp, phone, contact form, social, in person)."""
        c = conn()
        t = get_task(task_id)
        org = get_org(t["org_id"])
        channel = request.form.get("channel", "phone")
        note = request.form.get("note", "").strip()
        who = request.form.get("sent_by", "").strip()
        kind = "reply" if task_status(c, org) == "reply waiting" else "invite"
        try:
            if not note or not who:
                raise rules.RuleViolation("Say what was sent and who sent it.")
            rules.check_can_draft(c, org, kind, channel)
            issues = rules.copy_issues(note)
            if issues:
                raise rules.RuleViolation("Fix the message first: " + " ".join(issues))
        except rules.RuleViolation as exc:
            flash(str(exc), "error")
            return redirect(url_for("task", task_id=task_id))
        c.execute(
            """INSERT INTO outreach (org_id, task_id, kind, channel, language, subject, body, drafted_at, sent_at, sent_by)
               VALUES (?, ?, ?, ?, 'en', '', ?, ?, ?, ?)""",
            (org["id"], task_id, kind, channel, note, db.now(), db.now(), who),
        )
        c.commit()
        flash("Recorded.", "ok")
        return redirect(url_for("task", task_id=task_id))

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

    def deliver(row, org, reviewed):
        """Send one reviewed email draft from the founder's mailbox. Returns an error or None."""
        c = conn()
        box = mailbox()
        try:
            if row["channel"] != "email":
                raise rules.RuleViolation("Only emails can be sent from the engine; record other channels as contacted.")
            if box is None:
                raise rules.RuleViolation("The mailbox is not connected.")
            if not reviewed:
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
            message_id = box.send(org["contact_email"], row["subject"], row["body"], in_reply_to)
        except rules.RuleViolation as exc:
            return str(exc)
        except Exception as exc:  # network or login failure: nothing is marked sent
            return f"Not sent: {exc}"
        c.execute(
            "UPDATE outreach SET sent_at = ?, sent_by = ?, message_id = ? WHERE id = ?",
            (db.now(), box.user, message_id, row["id"]),
        )
        c.commit()
        return None

    @app.post("/outreach/<int:outreach_id>/send")
    def send(outreach_id):
        row = one("SELECT * FROM outreach WHERE id = ?", (outreach_id,))
        org = get_org(row["org_id"])
        error = deliver(row, org, request.form.get("reviewed") == "yes")
        if error:
            flash(error, "error")
            return redirect(url_for("outreach", outreach_id=outreach_id))
        flash(f"Sent from {mailbox().user}.", "ok")
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
        box = mailbox()
        if box is None:
            flash("The mailbox is not connected.", "error")
        else:
            run_mail_check(box, announce_nothing=True)
        return redirect(request.form.get("next") or url_for("overview"))

    def run_mail_check(box, announce_nothing=False):
        c = conn()
        c.execute("DELETE FROM meta WHERE key = 'mail_checked_at'")
        c.execute("INSERT INTO meta (key, value) VALUES ('mail_checked_at', ?)", (str(time.time()),))
        c.commit()
        try:
            result = box.fetch_replies(c)
        except Exception as exc:
            c.rollback()
            flash(f"Could not check the mailbox for replies: {exc}", "error")
            return
        if result["new"]:
            message = f"{result['new']} new repl{'y' if result['new'] == 1 else 'ies'}."
            if result["opt_outs"]:
                message += " Added to do not contact: " + ", ".join(result["opt_outs"]) + "."
            flash(message, "ok")
        elif announce_nothing:
            looked = result.get("looked_for")
            flash("No new replies." + (
                f" Looked in the inbox for answers to our emails and for mail from {', '.join(looked)}."
                if looked else " Nothing has been emailed yet, so there is nothing to look for."), "ok")

    def auto_check_mail():
        """Look for replies when a page opens, at most every two minutes, so nobody has to remember."""
        box = mailbox()
        if box is None:
            return
        row = conn().execute("SELECT value FROM meta WHERE key = 'mail_checked_at'").fetchone()
        if row and time.time() - float(row[0]) < 120:
            return
        if not conn().execute(
            "SELECT 1 FROM outreach WHERE sent_at IS NOT NULL AND channel = 'email' LIMIT 1"
        ).fetchone():
            return
        run_mail_check(box)

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

    @app.post("/mail/test")
    def test_mail():
        box = mailbox()
        if box is None:
            flash("The mailbox is not connected.", "error")
        else:
            try:
                flash(box.test(), "ok")
            except Exception as exc:
                flash(f"Mailbox test failed: {exc}", "error")
        return redirect(url_for("overview"))

    # Contact finder

    @app.post("/orgs/<int:org_id>/find-contacts")
    def find_contacts(org_id):
        org = get_org(org_id)
        result = finder.run_for_org(conn(), org, app.config["FETCH_PAGE"])
        message = f"Found {result['added']} new contact detail{'' if result['added'] == 1 else 's'}."
        if result["errors"]:
            message += " Could not read: " + "; ".join(result["errors"][:3])
        flash(message, "ok" if result["added"] or not result["errors"] else "error")
        return redirect(request.form.get("next") or url_for("organisation", org_id=org_id))

    @app.post("/suggestions/<int:suggestion_id>")
    def use_suggestion(suggestion_id):
        c = conn()
        s = one("SELECT * FROM contact_suggestions WHERE id = ?", (suggestion_id,))
        action = request.form.get("action")
        if action == "use":
            field = finder.FIELD_FOR_KIND[s["kind"]]
            value = rules.normalise_email(s["value"]) if s["kind"] == "email" else s["value"]
            c.execute(f"UPDATE organisations SET {field} = ? WHERE id = ?", (value, s["org_id"]))
            c.execute("UPDATE contact_suggestions SET status = 'used' WHERE id = ?", (suggestion_id,))
        elif action == "ignore":
            c.execute("UPDATE contact_suggestions SET status = 'ignored' WHERE id = ?", (suggestion_id,))
        c.commit()
        return redirect(request.form.get("next") or url_for("organisation", org_id=s["org_id"]))

    # Results by channel

    @app.get("/results")
    def results():
        c = conn()
        tasks = c.execute("SELECT approach_id, org_id, outcome FROM tasks").fetchall()
        contacted = {r["org_id"] for r in c.execute(
            "SELECT DISTINCT org_id FROM outreach WHERE sent_at IS NOT NULL AND kind = 'invite'")}
        replied = {r["org_id"] for r in c.execute("SELECT DISTINCT org_id FROM inbound")}
        enquiry_counts = {r["org_id"]: (r["n"], r["q"]) for r in c.execute(
            """SELECT source_org_id AS org_id, count(*) AS n,
                      sum(CASE WHEN ticket_fit IN ('lump_sum', 'sip') THEN 1 ELSE 0 END) AS q
               FROM enquiries WHERE source_org_id IS NOT NULL GROUP BY source_org_id""")}
        rows = []
        for a in c.execute("SELECT * FROM approaches ORDER BY country, name").fetchall():
            mine = [r for r in tasks if r["approach_id"] == a["id"]]
            org_ids = {r["org_id"] for r in mine}
            outcomes = [r["outcome"] for r in mine]
            rows.append({
                "approach": a,
                "targets": len(org_ids),
                "contacted": len(org_ids & contacted),
                "replied": len(org_ids & replied),
                "agreed": sum(o in ("agreed", "live") for o in outcomes),
                "live": sum(o == "live" for o in outcomes),
                "declined": sum(o == "declined" for o in outcomes),
                "enquiries": sum(enquiry_counts.get(o, (0, 0))[0] for o in org_ids),
                "qualified": sum(enquiry_counts.get(o, (0, 0))[1] or 0 for o in org_ids),
            })
        by_org = c.execute(
            """SELECT g.id, g.name, g.country, count(*) AS enquiries,
                      sum(CASE WHEN e.ticket_fit IN ('lump_sum', 'sip') THEN 1 ELSE 0 END) AS qualified
               FROM enquiries e JOIN organisations g ON g.id = e.source_org_id
               GROUP BY g.id, g.name, g.country ORDER BY count(*) DESC"""
        ).fetchall()
        unattributed = c.execute("SELECT count(*) FROM enquiries WHERE source_org_id IS NULL").fetchone()[0]
        return render_template("results.html", rows=rows, by_org=by_org, unattributed=unattributed)

    # Calendar and reminders

    def agenda(start, end):
        c = conn()
        items = []
        for r in c.execute(
            """SELECT * FROM calendar_items
               WHERE coalesce(end_date, date) >= ? AND date <= ? ORDER BY date""", (start, end)
        ):
            items.append({"date": r["date"], "end_date": r["end_date"], "title": r["title"], "kind": r["kind"],
                          "note": r["note"], "id": r["id"], "done": r["done"], "task_id": r["task_id"]})
        for t in tasks_for("t.next_action_date IS NOT NULL AND t.next_action_date <= ?", (end,)):
            items.append({"date": t["next_action_date"], "end_date": None, "kind": "task",
                          "title": f"{t['org']['name']}: {t['next_action'] or 'next step'}",
                          "note": t["approach_name"], "id": None, "done": 0, "task_id": t["task_id"]})
        for e in c.execute("SELECT * FROM events WHERE substr(starts_at, 1, 10) BETWEEN ? AND ?", (start, end)):
            items.append({"date": e["starts_at"][:10], "end_date": None, "kind": "webinar", "title": e["title"],
                          "note": f"{e['language']}, {e['cohort']}", "id": None, "done": 0, "task_id": None,
                          "event_id": e["id"]})
        return sorted(items, key=lambda i: i["date"])

    @app.route("/calendar", methods=["GET", "POST"])
    def calendar_page():
        c = conn()
        if request.method == "POST":
            f = request.form
            if f.get("action") == "done":
                c.execute("UPDATE calendar_items SET done = 1 WHERE id = ?", (f["id"],))
            elif f.get("date") and f.get("title", "").strip():
                c.execute(
                    """INSERT OR IGNORE INTO calendar_items (date, end_date, title, kind, country, note, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (f["date"], f.get("end_date") or None, f["title"].strip(), f.get("kind", "reminder"),
                     f.get("country") or None, f.get("note", "").strip() or None, db.now()),
                )
            else:
                flash("A calendar item needs a date and a title.", "error")
            c.commit()
            return redirect(url_for("calendar_page"))
        today = date.today()
        upcoming = agenda((today - timedelta(days=30)).isoformat(), (today + timedelta(days=365)).isoformat())
        return render_template("calendar.html", items=upcoming)

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
            suggestions=c.execute(
                "SELECT * FROM contact_suggestions WHERE org_id = ? AND status = 'new' ORDER BY kind", (org_id,)
            ).fetchall(),
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
