"""Import webinar registrations exported as CSV (for example from Google Forms).

Expected columns: name, email, country (two-letter code), consent_followup
(yes or no), consent_text (the exact wording the person agreed to).
"""

import csv
import io

from . import rules
from .db import now

REQUIRED = ("name", "email", "country", "consent_followup", "consent_text")
YES = {"yes", "y", "true", "1"}


def import_registrations(conn, event_id, csv_text):
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise rules.RuleViolation("CSV is missing columns: " + ", ".join(missing))

    report = {"added": 0, "duplicate": 0, "do_not_contact": 0, "invalid": []}
    for line, row in enumerate(reader, start=2):
        name = (row["name"] or "").strip()
        email = rules.normalise_email(row["email"])
        country = (row["country"] or "").strip().upper()
        consent_text = (row["consent_text"] or "").strip()
        if not name or "@" not in email or len(country) != 2 or not consent_text:
            report["invalid"].append(line)
            continue
        if rules.dnc_reason(conn, email=email, name=name):
            report["do_not_contact"] += 1
            continue
        cur = conn.execute(
            """INSERT OR IGNORE INTO registrations
               (event_id, name, email, country, consent_followup, consent_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                name,
                email,
                country,
                1 if (row["consent_followup"] or "").strip().lower() in YES else 0,
                consent_text,
                now(),
            ),
        )
        if cur.rowcount:
            report["added"] += 1
        else:
            report["duplicate"] += 1
    conn.commit()
    return report
