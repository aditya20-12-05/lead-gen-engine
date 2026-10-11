"""SQLite storage. One file on the wealth manager's laptop; nothing leaves it."""

import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS organisations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('community', 'employer', 'media')),
    country TEXT NOT NULL,
    city TEXT,
    contact_email TEXT,
    website TEXT,
    source_url TEXT NOT NULL,
    source_note TEXT,
    source_checked_at TEXT,
    source_status TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (name, country)
);

-- Country > approach > task. An approach is a channel in one country (for
-- example "Weekly newspaper column" in the UK) with SELEQT's brief for it.
CREATE TABLE IF NOT EXISTS approaches (
    id INTEGER PRIMARY KEY,
    country TEXT NOT NULL,
    name TEXT NOT NULL,
    our_brief TEXT NOT NULL,
    template_kind TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('planned', 'active', 'paused')),
    created_at TEXT NOT NULL,
    UNIQUE (country, name)
);

-- One task per organisation within an approach.
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    approach_id INTEGER NOT NULL REFERENCES approaches (id),
    org_id INTEGER NOT NULL REFERENCES organisations (id),
    plan TEXT,
    owner TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (approach_id, org_id)
);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organisations (id),
    kind TEXT NOT NULL CHECK (kind IN ('invite', 'reply')),
    language TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    drafted_at TEXT NOT NULL,
    sent_at TEXT,
    sent_by TEXT
);

CREATE TABLE IF NOT EXISTS inbound (
    id INTEGER PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organisations (id),
    received_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    body TEXT NOT NULL
);

-- Permanent: the app offers no way to delete rows from this table.
CREATE TABLE IF NOT EXISTS dnc (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('email', 'domain', 'name', 'phone')),
    value TEXT NOT NULL,
    reason TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (kind, value)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    language TEXT NOT NULL,
    cohort TEXT NOT NULL,
    host_org_id INTEGER REFERENCES organisations (id),
    platform TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events (id),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    country TEXT NOT NULL,
    consent_followup INTEGER NOT NULL,
    consent_text TEXT NOT NULL,
    followed_up_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (event_id, email)
);

CREATE TABLE IF NOT EXISTS enquiries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    country TEXT NOT NULL,
    citizenship TEXT,
    oci INTEGER,
    family_key TEXT NOT NULL,
    route TEXT NOT NULL DEFAULT 'undecided' CHECK (route IN ('undecided', 'RIA', 'MFD')),
    first_contact_at TEXT NOT NULL,
    first_contact_channel TEXT NOT NULL,
    first_message TEXT NOT NULL,
    ticket_fit TEXT NOT NULL DEFAULT 'unknown'
        CHECK (ticket_fit IN ('unknown', 'lump_sum', 'sip', 'below')),
    source_event_id INTEGER REFERENCES events (id),
    source_org_id INTEGER REFERENCES organisations (id),
    notes TEXT,
    created_at TEXT NOT NULL
);
"""


def now():
    # Microseconds keep message order unambiguous when two events share a second.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release; added in place on older databases.
MIGRATIONS = {
    "outreach": {"task_id": "INTEGER REFERENCES tasks (id)", "message_id": "TEXT"},
    "inbound": {
        "task_id": "INTEGER REFERENCES tasks (id)",
        "message_id": "TEXT",
        "from_addr": "TEXT",
        "subject": "TEXT",
    },
}


def init(conn):
    conn.executescript(SCHEMA)
    for table, columns in MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS inbound_message_id ON inbound (message_id) "
        "WHERE message_id IS NOT NULL"
    )
    conn.commit()
