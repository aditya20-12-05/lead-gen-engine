"""Send email from the founder's Zoho mailbox and catch replies, over SMTP and IMAP.

Defaults are Zoho India (smtp.zoho.in, imap.zoho.in) and ishit@seleqtwealth.in.
The only required setting is SELEQT_MAIL_PASSWORD, a Zoho app password, read
from the environment and never stored in the repository. SELEQT_MAIL_USER,
SELEQT_SMTP_HOST, SELEQT_SMTP_PORT, SELEQT_IMAP_HOST, SELEQT_IMAP_PORT and
SELEQT_IMAP_SENT override the defaults.

Nothing here sends on its own: send() runs only when a person presses Send on
a reviewed draft. Reply checks open the inbox read-only and never mark mail
as read.
"""

import email
import email.policy
import imaplib
import os
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from . import rules
from .db import now

OPT_OUT_PHRASES = (
    "unsubscribe",
    "remove me",
    "remove us",
    "do not contact",
    "don't contact",
    "do not email",
    "stop emailing",
    "no further emails",
)


@dataclass
class MailConfig:
    user: str
    password: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    sent_folder: str | None
    from_name: str

    @classmethod
    def from_env(cls, from_name=""):
        env = os.environ
        if not env.get("SELEQT_MAIL_PASSWORD"):
            return None
        return cls(
            user=env.get("SELEQT_MAIL_USER", "ishit@seleqtwealth.in"),
            password=env["SELEQT_MAIL_PASSWORD"],
            smtp_host=env.get("SELEQT_SMTP_HOST", "smtp.zoho.in"),
            smtp_port=int(env.get("SELEQT_SMTP_PORT", "465")),
            imap_host=env.get("SELEQT_IMAP_HOST", "imap.zoho.in"),
            imap_port=int(env.get("SELEQT_IMAP_PORT", "993")),
            sent_folder=env.get("SELEQT_IMAP_SENT") or None,
            from_name=from_name,
        )


def build_message(config, to, subject, body, in_reply_to=None):
    msg = EmailMessage()
    msg["From"] = formataddr((config.from_name, config.user)) if config.from_name else config.user
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=config.user.split("@", 1)[1])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    return msg


def send(config, msg):
    context = ssl.create_default_context()
    if config.smtp_port == 465:
        server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context, timeout=30)
    else:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
        server.starttls(context=context)
    with server:
        server.login(config.user, config.password)
        server.send_message(msg)
    if config.sent_folder:
        with imaplib.IMAP4_SSL(config.imap_host, config.imap_port) as imap:
            imap.login(config.user, config.password)
            imap.append(config.sent_folder, r"(\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    return msg["Message-ID"]


def plain_text(message):
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    if part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_opt_out(text):
    lowered = text.lower()
    return any(phrase in lowered for phrase in OPT_OUT_PHRASES)


def _imap_date(iso_ts):
    return time.strftime("%d-%b-%Y", time.strptime(iso_ts[:10], "%Y-%m-%d"))


def fetch_replies(conn, config, imap_factory=None):
    """Store replies from organisations we have emailed. Returns a summary."""
    contacted = conn.execute(
        """SELECT g.id AS org_id, lower(g.contact_email) AS email, min(o.sent_at) AS first_sent,
                  (SELECT o2.task_id FROM outreach o2 WHERE o2.org_id = g.id AND o2.sent_at IS NOT NULL
                   ORDER BY o2.sent_at DESC LIMIT 1) AS task_id
           FROM outreach o JOIN organisations g ON g.id = o.org_id
           WHERE o.sent_at IS NOT NULL AND g.contact_email IS NOT NULL
           GROUP BY g.id"""
    ).fetchall()
    summary = {"new": 0, "opt_outs": []}
    if not contacted:
        return summary
    factory = imap_factory or (lambda: imaplib.IMAP4_SSL(config.imap_host, config.imap_port))
    imap = factory()
    try:
        imap.login(config.user, config.password)
        imap.select("INBOX", readonly=True)
        for row in contacted:
            status, data = imap.search(None, "FROM", f'"{row["email"]}"', "SINCE", _imap_date(row["first_sent"]))
            if status != "OK":
                continue
            for num in data[0].split():
                status, parts = imap.fetch(num, "(BODY.PEEK[])")
                if status != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                message = email.message_from_bytes(parts[0][1], policy=email.policy.default)
                if parseaddr(message.get("From", ""))[1].lower() != row["email"]:
                    continue
                message_id = (message.get("Message-ID") or "").strip() or None
                body = plain_text(message)
                cur = conn.execute(
                    """INSERT OR IGNORE INTO inbound
                       (org_id, task_id, received_at, channel, body, message_id, from_addr, subject)
                       VALUES (?, ?, ?, 'email', ?, ?, ?, ?)""",
                    (row["org_id"], row["task_id"], now(), body, message_id, row["email"],
                     str(message.get("Subject", ""))),
                )
                if cur.rowcount:
                    summary["new"] += 1
                    if is_opt_out(body):
                        rules.add_dnc(conn, "email", row["email"], "Asked not to be contacted (reply detected)")
                        summary["opt_outs"].append(row["email"])
        conn.commit()
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return summary
