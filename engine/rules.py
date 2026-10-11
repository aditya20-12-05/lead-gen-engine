"""Guardrails. Every outbound step passes through these checks.

The rules come from SELEQT's own constraints: a permanent do-not-contact list,
nobody contacted twice, house style for copy, SEBI advertisement code red
flags, RIA and MFD segregation, and no follow-up marketing where local law
makes it risky.
"""

import re

# Gulf residents: SELEQT approaches only the community body, and replies only
# to people who contact it first. No follow-up marketing to attendees.
NO_FOLLOWUP_COUNTRIES = {"AE", "QA", "OM", "BH", "KW", "SA"}

# Phrases the SEBI advertisement code treats as misleading for registered
# intermediaries (assured returns, superlatives, risk-free claims).
SEBI_RED_FLAGS = [
    "guarantee",
    "guaranteed",
    "assured return",
    "assured returns",
    "risk free",
    "risk-free",
    "no risk",
    "sure shot",
    "safe returns",
    "double your money",
    "best returns",
    "best fund",
    "number one",
    "no. 1",
    "top performing",
]

WEBMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "live.com"}

DASHES = {"\u2014": "em dash", "\u2013": "en dash", "\u2012": "figure dash", "\u2015": "horizontal bar"}


class RuleViolation(Exception):
    pass


def normalise_email(email):
    return (email or "").strip().lower()


def email_domain(email):
    email = normalise_email(email)
    return email.split("@", 1)[1] if "@" in email else ""


def dnc_reason(conn, *, email=None, name=None, phone=None):
    """Return the do-not-contact reason if any identifier is listed, else None."""
    checks = []
    if email:
        checks.append(("email", normalise_email(email)))
        domain = email_domain(email)
        if domain:
            checks.append(("domain", domain))
    if name:
        checks.append(("name", name.strip().lower()))
    if phone:
        checks.append(("phone", re.sub(r"\D", "", phone)))
    for kind, value in checks:
        row = conn.execute(
            "SELECT reason FROM dnc WHERE kind = ? AND value = ?", (kind, value)
        ).fetchone()
        if row:
            return f"{kind} {value}: {row['reason']}"
    return None


def add_dnc(conn, kind, value, reason):
    if kind == "email":
        value = normalise_email(value)
    elif kind == "phone":
        value = re.sub(r"\D", "", value)
    else:
        value = value.strip().lower()
    if not value or not reason.strip():
        raise RuleViolation("Do-not-contact entries need a value and a reason.")
    if kind == "domain" and value in WEBMAIL_DOMAINS:
        raise RuleViolation(
            f"{value} is shared webmail; block the individual email address instead."
        )
    conn.execute(
        "INSERT OR IGNORE INTO dnc (kind, value, reason, added_at) VALUES (?, ?, ?, datetime('now'))",
        (kind, value, reason.strip()),
    )
    conn.commit()


def house_style_issues(text):
    """House style: no em or en dashes, SELEQT always in capitals."""
    issues = []
    for char, label in DASHES.items():
        if char in text:
            issues.append(f"Contains an {label}; use a comma or parentheses instead.")
    for match in re.finditer(r"seleqt", text, flags=re.IGNORECASE):
        if match.group(0) != "SELEQT":
            issues.append(f"'{match.group(0)}' must be written as SELEQT.")
            break
    return issues


def compliance_issues(text):
    lowered = text.lower()
    return [
        f"SEBI advertisement code red flag: '{phrase}'."
        for phrase in SEBI_RED_FLAGS
        if re.search(r"\b" + re.escape(phrase) + r"\b", lowered)
    ]


def placeholder_issues(text):
    return [f"Fill in the placeholder {p}." for p in sorted(set(re.findall(r"\[[^\]\n]+\]", text)))]


def copy_issues(text):
    return house_style_issues(text) + compliance_issues(text) + placeholder_issues(text)


def org_already_invited(conn, org_id, contact_email):
    """Nobody contacted twice: one invite per organisation and per address, ever."""
    row = conn.execute(
        "SELECT 1 FROM outreach WHERE kind = 'invite' AND sent_at IS NOT NULL AND org_id = ?",
        (org_id,),
    ).fetchone()
    if row:
        return True
    email = normalise_email(contact_email)
    if not email:
        return False
    row = conn.execute(
        """SELECT 1 FROM outreach o JOIN organisations g ON g.id = o.org_id
           WHERE o.kind = 'invite' AND o.sent_at IS NOT NULL AND lower(g.contact_email) = ?""",
        (email,),
    ).fetchone()
    return row is not None


def awaiting_our_reply(conn, org_id):
    """A reply is allowed only when the organisation wrote after our last message."""
    last_in = conn.execute(
        "SELECT max(received_at) AS t FROM inbound WHERE org_id = ?", (org_id,)
    ).fetchone()["t"]
    if not last_in:
        return False
    last_out = conn.execute(
        "SELECT max(sent_at) AS t FROM outreach WHERE org_id = ? AND sent_at IS NOT NULL",
        (org_id,),
    ).fetchone()["t"]
    return last_out is None or last_in > last_out


def check_can_draft(conn, org, kind):
    reason = dnc_reason(conn, email=org["contact_email"], name=org["name"])
    if reason:
        raise RuleViolation(f"On the do-not-contact list ({reason}).")
    if not org["contact_email"]:
        raise RuleViolation("No official contact email recorded for this organisation.")
    if kind == "invite" and org_already_invited(conn, org["id"], org["contact_email"]):
        raise RuleViolation("Already emailed once. Nobody is contacted twice.")
    if kind == "reply" and not awaiting_our_reply(conn, org["id"]):
        raise RuleViolation("No new message from them to reply to.")


def check_can_mark_sent(conn, outreach_row, org):
    if outreach_row["sent_at"]:
        raise RuleViolation("This draft is already marked as sent.")
    check_can_draft(conn, org, outreach_row["kind"])
    issues = copy_issues(outreach_row["subject"] + "\n" + outreach_row["body"])
    if issues:
        raise RuleViolation("Fix the copy first: " + " ".join(issues))


def followup_allowed(registration):
    """One follow-up at most, only with consent, never to Gulf residents."""
    if not registration["consent_followup"] or registration["followed_up_at"]:
        return False
    return registration["country"].upper() not in NO_FOLLOWUP_COUNTRIES


def check_route(conn, enquiry_id, family_key, route):
    """RIA and MFD segregation: one family is served by one side only."""
    if route == "undecided":
        return
    row = conn.execute(
        """SELECT route FROM enquiries
           WHERE family_key = ? AND id != ? AND route NOT IN ('undecided', ?)""",
        (family_key, enquiry_id or 0, route),
    ).fetchone()
    if row:
        raise RuleViolation(
            f"This family is already on the {row['route']} side. RIA and MFD stay separate."
        )
