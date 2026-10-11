"""The founder's mailbox (ishit@seleqtwealth.in on Zoho): send email and catch replies.

Two ways to reach it, chosen from the environment:

- Zoho Mail API over HTTPS (used when hosted, since free hosts block mail
  ports): SELEQT_ZOHO_CLIENT_ID, SELEQT_ZOHO_CLIENT_SECRET,
  SELEQT_ZOHO_REFRESH_TOKEN; optional SELEQT_ZOHO_ACCOUNTS_URL (default
  https://accounts.zoho.in) and SELEQT_ZOHO_MAIL_URL (default https://mail.zoho.in).
- SMTP and IMAP: SELEQT_MAIL_PASSWORD (a Zoho app password); optional
  SELEQT_SMTP_HOST, SELEQT_SMTP_PORT, SELEQT_IMAP_HOST, SELEQT_IMAP_PORT,
  SELEQT_IMAP_SENT.

SELEQT_MAIL_USER overrides the address. Secrets are read from the environment
only, never stored in the repository.

Nothing here sends on its own: send() runs only when a person presses Send on
a reviewed draft. Reply checks only read, and never mark mail as read.
"""

import calendar
import email
import email.policy
import html
import imaplib
import json
import os
import re
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from . import rules
from .db import now

DEFAULT_USER = "ishit@seleqtwealth.in"

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


def is_opt_out(text):
    lowered = text.lower()
    return any(phrase in lowered for phrase in OPT_OUT_PHRASES)


def html_to_text(markup):
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def contacted_orgs(conn):
    """Organisations we have emailed, with the date of our first email."""
    return conn.execute(
        """SELECT g.id AS org_id, lower(g.contact_email) AS email, min(o.sent_at) AS first_sent,
                  (SELECT o2.task_id FROM outreach o2 WHERE o2.org_id = g.id AND o2.sent_at IS NOT NULL
                   ORDER BY o2.sent_at DESC LIMIT 1) AS task_id
           FROM outreach o JOIN organisations g ON g.id = o.org_id
           WHERE o.sent_at IS NOT NULL AND o.channel = 'email' AND g.contact_email IS NOT NULL
           GROUP BY g.id, g.contact_email"""
    ).fetchall()


def sent_message_ids(conn):
    """Message-IDs of the emails we sent, so replies can be matched by thread."""
    rows = conn.execute(
        """SELECT o.id AS outreach_id, o.message_id, o.org_id, o.task_id, lower(g.contact_email) AS email
           FROM outreach o JOIN organisations g ON g.id = o.org_id
           WHERE o.sent_at IS NOT NULL AND o.channel = 'email' AND o.message_id IS NOT NULL"""
    ).fetchall()
    return {r["message_id"].strip(): r for r in rows}


# Bounces: "undelivered" notices from the receiving side.

BOUNCE_SENDERS = {"mailer-daemon", "mailerdaemon", "postmaster", "mail-daemon"}
BOUNCE_SUBJECT = re.compile(
    r"(?i)undeliver|delivery status notification \(failure\)|delivery failure|failure notice|returned mail|"
    r"mail delivery failed|delivery has failed|not delivered|could not be delivered|delivery incomplete"
)
REASON_CODE = re.compile(r"\b[45]\d\d[\s-]+[45]\.\d{1,3}\.\d{1,3}\b[^\n]*")
REASON_LINE = re.compile(r"(?m)^\s*[45]\d\d\b[^\n]*")
REASON_WORDS = re.compile(
    r"(?i)[^\n]*(does not exist|doesn't exist|not found|unknown user|user unknown|no such user|"
    r"mailbox unavailable|address rejected|rejected|quota|mailbox full|spf|dkim|dmarc|blocked|spam|"
    r"couldn't be found|could not be found|unable to receive)[^\n]*"
)


def looks_like_bounce(headers, contacted_addresses=()):
    sender = parseaddr(str(headers.get("From", "")))[1].lower()
    subject = str(headers.get("Subject", ""))
    content_type = re.sub(r'[\s"]', "", str(headers.get("Content-Type", "")).lower())
    if re.search(r"(?i)\bdelay", subject):
        return False  # "still trying" warnings, not failures
    if sender.split("@")[0] in BOUNCE_SENDERS or "report-type=delivery-status" in content_type:
        return True
    return bool(BOUNCE_SUBJECT.search(subject)) and sender not in contacted_addresses


def parse_bounce(message, raw_text):
    """Failed recipients, the reason given, and whether it is a real failure."""
    recipients, diagnostic, actions = [], None, []
    for part in message.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        payload = part.get_payload()
        for block in payload if isinstance(payload, list) else []:
            for key in ("Final-Recipient", "Original-Recipient"):
                if block.get(key):
                    recipients.append(str(block.get(key)).split(";")[-1].strip().strip("<>").lower())
            if block.get("Diagnostic-Code") and not diagnostic:
                diagnostic = " ".join(str(block.get("Diagnostic-Code")).split(";", 1)[-1].split())
            if block.get("Action"):
                actions.append(str(block.get("Action")).strip().lower())
    if actions and not any(a == "failed" for a in actions):
        return recipients, None, False  # delayed, delivered or relayed
    reason = diagnostic
    if not reason:
        text = plain_text(message) or raw_text
        found = REASON_CODE.search(text) or REASON_LINE.search(text) or REASON_WORDS.search(text)
        reason = " ".join(found.group(0).split()) if found else None
    return recipients, (reason or "Returned as undeliverable; no reason given.")[:300], True


def record_bounce(conn, message, raw_text, by_message, summary):
    recipients, reason, failed = parse_bounce(message, raw_text)
    if not failed:
        return
    row = next((r for mid, r in by_message.items() if mid in raw_text), None)
    address = row["email"] if row is not None else None
    if row is None:
        sent = conn.execute(
            """SELECT o.id AS outreach_id, o.org_id, lower(coalesce(o.to_addr, g.contact_email)) AS addr
               FROM outreach o JOIN organisations g ON g.id = o.org_id
               WHERE o.sent_at IS NOT NULL AND o.channel = 'email' ORDER BY o.sent_at"""
        ).fetchall()
        by_addr = {r["addr"]: r for r in sent if r["addr"]}
        candidates = recipients or [a for a in by_addr if re.search(r"(?<![\w.+-])" + re.escape(a) + r"(?![\w-])",
                                                                  raw_text, re.I)]
        row = next((by_addr[a] for a in candidates if a in by_addr), None)
        address = row["addr"] if row is not None else None
    if row is None:
        return
    address = recipients[0] if recipients else address
    cur = conn.execute(
        "UPDATE outreach SET bounced_at = ?, bounce_reason = ?, to_addr = coalesce(to_addr, ?) "
        "WHERE id = ? AND bounced_at IS NULL",
        (now(), reason, address, row["outreach_id"]),
    )
    if cur.rowcount:
        summary["bounced"].append(address)


def store_reply(conn, row, message_id, subject, body, summary, from_addr=None):
    from_addr = from_addr or row["email"]
    cur = conn.execute(
        """INSERT OR IGNORE INTO inbound
           (org_id, task_id, received_at, channel, body, message_id, from_addr, subject)
           VALUES (?, ?, ?, 'email', ?, ?, ?, ?)""",
        (row["org_id"], row["task_id"], now(), body, message_id, from_addr, subject),
    )
    if cur.rowcount:
        summary["new"] += 1
        if is_opt_out(body):
            for address in {row["email"], from_addr} - {None, ""}:
                rules.add_dnc(conn, "email", address, "Asked not to be contacted (reply detected)")
                summary["opt_outs"].append(address)


# SMTP and IMAP

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
            user=env.get("SELEQT_MAIL_USER", DEFAULT_USER),
            password=env["SELEQT_MAIL_PASSWORD"],
            smtp_host=env.get("SELEQT_SMTP_HOST", "smtp.zoho.in"),
            smtp_port=int(env.get("SELEQT_SMTP_PORT", "465")),
            imap_host=env.get("SELEQT_IMAP_HOST", "imap.zoho.in"),
            imap_port=int(env.get("SELEQT_IMAP_PORT", "993")),
            sent_folder=env.get("SELEQT_IMAP_SENT") or None,
            from_name=from_name,
        )


def build_message(config, to, subject, body, in_reply_to=None, body_html=None):
    msg = EmailMessage()
    msg["From"] = formataddr((config.from_name, config.user)) if config.from_name else config.user
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=config.user.split("@", 1)[1])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg


def plain_text(message):
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    if part.get_content_type() == "text/html":
        return html_to_text(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _imap_date(iso_ts):
    return time.strftime("%d-%b-%Y", time.strptime(iso_ts[:10], "%Y-%m-%d"))


class SmtpMailbox:
    kind = "Zoho (SMTP and IMAP)"

    def __init__(self, config, imap_factory=None, smtp_factory=None):
        self.config = config
        self.user = config.user
        self._imap_factory = imap_factory or (lambda: imaplib.IMAP4_SSL(config.imap_host, config.imap_port))
        self._smtp_factory = smtp_factory

    def send(self, to, subject, body, in_reply_to=None, body_html=None):
        config = self.config
        msg = build_message(config, to, subject, body, in_reply_to, body_html)
        with self._smtp() as server:
            server.login(config.user, config.password)
            server.send_message(msg)
        if config.sent_folder:
            imap = self._imap_factory()
            imap.login(config.user, config.password)
            imap.append(config.sent_folder, r"(\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            imap.logout()
        return msg["Message-ID"]

    def fetch_replies(self, conn):
        """Read-only pass over the inbox since our first email.

        A message counts as a reply when it answers one of our emails (In-Reply-To
        or References carries our Message-ID), whoever sent it, or when it comes
        from the address we wrote to. Our own sent copies are skipped.
        """
        summary = {"new": 0, "opt_outs": [], "looked_for": [], "bounced": []}
        contacted = contacted_orgs(conn)
        if not contacted:
            return summary
        by_email = {r["email"]: r for r in contacted}
        by_message = sent_message_ids(conn)
        summary["looked_for"] = sorted(by_email)
        since = min(r["first_sent"] for r in contacted)
        imap = self._imap_factory()
        try:
            imap.login(self.config.user, self.config.password)
            imap.select("INBOX", readonly=True)
            status, data = imap.search(None, "SINCE", _imap_date(since))
            nums = data[0].split() if status == "OK" and data and data[0] else []
            matched, bounces = [], []
            for chunk in range(0, len(nums), 200):
                status, parts = imap.fetch(
                    b",".join(nums[chunk:chunk + 200]),
                    "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT CONTENT-TYPE MESSAGE-ID IN-REPLY-TO REFERENCES)])",
                )
                if status != "OK":
                    continue
                for part in parts or []:
                    if not isinstance(part, tuple):
                        continue
                    num = part[0].split()[0]
                    headers = email.message_from_bytes(part[1], policy=email.policy.default)
                    message_id = (headers.get("Message-ID") or "").strip()
                    if message_id in by_message:
                        continue  # our own email (a copy to ourselves)
                    if looks_like_bounce(headers, by_email):
                        bounces.append(num)
                        continue
                    refs = re.findall(r"<[^>]+>", f"{headers.get('In-Reply-To', '')} {headers.get('References', '')}")
                    row = next((by_message[ref] for ref in refs if ref in by_message), None)
                    sender = parseaddr(str(headers.get("From", "")))[1].lower()
                    if row is None:
                        row = by_email.get(sender)
                    if row is None or sender == self.config.user.lower() and not refs:
                        continue
                    if message_id and conn.execute(
                        "SELECT 1 FROM inbound WHERE message_id = ?", (message_id,)
                    ).fetchone():
                        continue
                    matched.append((num, row, sender))
            for num, row, sender in matched:
                status, parts = imap.fetch(num, "(BODY.PEEK[])")
                if status != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                message = email.message_from_bytes(parts[0][1], policy=email.policy.default)
                message_id = (message.get("Message-ID") or "").strip() or None
                store_reply(conn, row, message_id, str(message.get("Subject", "")), plain_text(message), summary,
                            from_addr=sender)
            for num in bounces:
                status, parts = imap.fetch(num, "(BODY.PEEK[])")
                if status != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                raw = parts[0][1]
                message = email.message_from_bytes(raw, policy=email.policy.default)
                record_bounce(conn, message, raw.decode("utf-8", "replace"), by_message, summary)
            conn.commit()
        finally:
            try:
                imap.logout()
            except Exception:
                pass
        return summary

    def _smtp(self):
        config = self.config
        if self._smtp_factory:
            return self._smtp_factory()
        if config.smtp_port == 465:
            return smtplib.SMTP_SSL(config.smtp_host, config.smtp_port,
                                    context=ssl.create_default_context(), timeout=30)
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
        server.starttls(context=ssl.create_default_context())
        return server

    def test(self):
        """Sign in for reading (IMAP) and for sending (SMTP), without sending anything."""
        try:
            imap = self._imap_factory()
            imap.login(self.config.user, self.config.password)
            imap.logout()
        except Exception as exc:
            raise RuntimeError(f"reading mail (IMAP) failed: {exc}") from exc
        try:
            with self._smtp() as server:
                server.login(self.config.user, self.config.password)
        except Exception as exc:
            raise RuntimeError(f"reading works, but sending (SMTP) failed: {exc}") from exc
        return f"Connected to {self.user}: reading and sending both work. Nothing was sent."


# Zoho Mail API

def _http_json(method, url, data=None, headers=None, form=False, timeout=30):
    body = None
    headers = dict(headers or {})
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


@dataclass
class ZohoConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    user: str
    accounts_url: str
    mail_url: str
    from_name: str

    @classmethod
    def from_env(cls, from_name=""):
        env = os.environ
        keys = ("SELEQT_ZOHO_CLIENT_ID", "SELEQT_ZOHO_CLIENT_SECRET", "SELEQT_ZOHO_REFRESH_TOKEN")
        if not all(env.get(k) for k in keys):
            return None
        return cls(
            client_id=env["SELEQT_ZOHO_CLIENT_ID"],
            client_secret=env["SELEQT_ZOHO_CLIENT_SECRET"],
            refresh_token=env["SELEQT_ZOHO_REFRESH_TOKEN"],
            user=env.get("SELEQT_MAIL_USER", DEFAULT_USER),
            accounts_url=env.get("SELEQT_ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in").rstrip("/"),
            mail_url=env.get("SELEQT_ZOHO_MAIL_URL", "https://mail.zoho.in").rstrip("/"),
            from_name=from_name,
        )


@dataclass
class ZohoMailbox:
    config: ZohoConfig
    http: object = _http_json
    kind: str = "Zoho Mail API"
    _token: str | None = field(default=None, repr=False)
    _token_expires: float = 0.0
    _account_id: str | None = None

    @property
    def user(self):
        return self.config.user

    def _access_token(self):
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        result = self.http("POST", f"{self.config.accounts_url}/oauth/v2/token", data={
            "refresh_token": self.config.refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
        }, form=True)
        if "access_token" not in result:
            raise RuntimeError(f"Zoho did not issue an access token: {result.get('error', result)}")
        self._token = result["access_token"]
        self._token_expires = time.time() + int(result.get("expires_in", 3600))
        return self._token

    def _api(self, method, path, data=None):
        headers = {"Authorization": f"Zoho-oauthtoken {self._access_token()}"}
        return self.http(method, f"{self.config.mail_url}/api{path}", data=data, headers=headers)

    def _account(self):
        if self._account_id:
            return self._account_id
        accounts = self._api("GET", "/accounts").get("data", [])
        for account in accounts:
            addresses = {str(account.get("primaryEmailAddress", "")).lower(),
                         str(account.get("mailboxAddress", "")).lower()}
            if self.user.lower() in addresses:
                self._account_id = str(account["accountId"])
                return self._account_id
        if len(accounts) == 1:
            self._account_id = str(accounts[0]["accountId"])
            return self._account_id
        raise RuntimeError(f"No Zoho mail account found for {self.user}.")

    def send(self, to, subject, body, in_reply_to=None, body_html=None):
        account = self._account()
        payload = {
            "fromAddress": f"{self.config.from_name} <{self.user}>" if self.config.from_name else self.user,
            "toAddress": to,
            "subject": subject,
            "content": body_html or body,
            "mailFormat": "html" if body_html else "plaintext",
        }
        if in_reply_to and in_reply_to.startswith("zoho:"):
            payload["action"] = "reply"
            result = self._api("POST", f"/accounts/{account}/messages/{in_reply_to[5:]}", payload)
        else:
            result = self._api("POST", f"/accounts/{account}/messages", payload)
        message_id = (result.get("data") or {}).get("messageId")
        return f"zoho:{message_id}" if message_id else None

    def fetch_replies(self, conn):
        summary = {"new": 0, "opt_outs": []}
        contacted = contacted_orgs(conn)
        if not contacted:
            return summary
        account = self._account()
        for row in contacted:
            first_sent_ms = calendar.timegm(time.strptime(row["first_sent"][:19], "%Y-%m-%dT%H:%M:%S")) * 1000
            query = urllib.parse.urlencode({"searchKey": f"sender:{row['email']}", "limit": 50})
            found = self._api("GET", f"/accounts/{account}/messages/search?{query}").get("data", [])
            for item in found:
                sender = parseaddr(str(item.get("fromAddress", "")))[1].lower() or str(item.get("sender", "")).lower()
                if sender != row["email"] or int(item.get("receivedTime", 0)) < first_sent_ms:
                    continue
                message_id = f"zoho:{item['messageId']}"
                if conn.execute("SELECT 1 FROM inbound WHERE message_id = ?", (message_id,)).fetchone():
                    continue
                content = self._api(
                    "GET", f"/accounts/{account}/folders/{item['folderId']}/messages/{item['messageId']}/content"
                ).get("data", {}).get("content", "")
                store_reply(conn, row, message_id, str(item.get("subject", "")), html_to_text(content), summary)
        conn.commit()
        return summary

    def test(self):
        account = self._account()
        return f"Connected to {self.user} through the Zoho Mail API (account {account})."


def mailbox_from_env(from_name=""):
    zoho = ZohoConfig.from_env(from_name)
    if zoho:
        return ZohoMailbox(zoho)
    smtp = MailConfig.from_env(from_name)
    if smtp:
        return SmtpMailbox(smtp)
    return None
