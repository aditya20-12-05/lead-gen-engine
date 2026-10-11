"""Storage. SQLite for a single computer, Postgres (DATABASE_URL) when hosted.

The app writes SQLite-style SQL ("?" placeholders, INSERT OR IGNORE); the
Postgres connection translates it, so both backends run the same queries.
"""

import re
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS organisations (
    id {pk},
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
    id {pk},
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
    id {pk},
    approach_id INTEGER NOT NULL REFERENCES approaches (id),
    org_id INTEGER NOT NULL REFERENCES organisations (id),
    plan TEXT,
    owner TEXT,
    outcome TEXT NOT NULL DEFAULT 'open' CHECK (outcome IN ('open', 'agreed', 'live', 'declined')),
    next_action TEXT,
    next_action_date TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (approach_id, org_id)
);

CREATE TABLE IF NOT EXISTS outreach (
    id {pk},
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
    id {pk},
    org_id INTEGER NOT NULL REFERENCES organisations (id),
    received_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    body TEXT NOT NULL
);

-- Permanent: the app offers no way to delete rows from this table.
CREATE TABLE IF NOT EXISTS dnc (
    id {pk},
    kind TEXT NOT NULL CHECK (kind IN ('email', 'domain', 'name', 'phone')),
    value TEXT NOT NULL,
    reason TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (kind, value)
);

CREATE TABLE IF NOT EXISTS events (
    id {pk},
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    language TEXT NOT NULL,
    cohort TEXT NOT NULL,
    host_org_id INTEGER REFERENCES organisations (id),
    platform TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    id {pk},
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
    id {pk},
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

-- Dated items for the calendar: webinars, deadlines, festivals, seasons, reminders.
CREATE TABLE IF NOT EXISTS calendar_items (
    id {pk},
    date TEXT NOT NULL,
    end_date TEXT,
    title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('webinar', 'deadline', 'festival', 'season', 'reminder')),
    country TEXT,
    task_id INTEGER REFERENCES tasks (id),
    note TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (date, title)
);

-- Contact details the contact finder found on an organisation's own pages,
-- waiting for a person to accept or ignore them.
CREATE TABLE IF NOT EXISTS contact_suggestions (
    id {pk},
    org_id INTEGER NOT NULL REFERENCES organisations (id),
    kind TEXT NOT NULL CHECK (kind IN ('email', 'phone', 'contact_form', 'social')),
    value TEXT NOT NULL,
    found_on TEXT NOT NULL,
    found_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'used', 'ignored')),
    UNIQUE (org_id, kind, value)
);
"""


# Columns added after the first release; added in place on older databases.
MIGRATIONS = {
    "organisations": {"contact_phone": "TEXT", "contact_form_url": "TEXT", "social_url": "TEXT"},
    "tasks": {
        "outcome": "TEXT NOT NULL DEFAULT 'open'",
        "next_action": "TEXT",
        "next_action_date": "TEXT",
    },
    "outreach": {
        "task_id": "INTEGER REFERENCES tasks (id)",
        "message_id": "TEXT",
        "channel": "TEXT NOT NULL DEFAULT 'email'",
    },
    "inbound": {
        "task_id": "INTEGER REFERENCES tasks (id)",
        "message_id": "TEXT",
        "from_addr": "TEXT",
        "subject": "TEXT",
    },
}


def now():
    # Microseconds keep message order unambiguous when two events share a second.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Row(dict):
    """A result row readable by column name or by position, like sqlite3.Row."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PgCursor:
    def __init__(self, cursor, returning):
        self._cursor = cursor
        self.rowcount = cursor.rowcount
        self.lastrowid = None
        if returning and cursor.description:
            row = cursor.fetchone()
            self.lastrowid = row[0] if row else None

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor.fetchall())


def _row_factory(cursor):
    names = [d.name for d in cursor.description or []]
    return lambda values: Row(zip(names, values))


def translate(sql):
    """SQLite dialect to Postgres: placeholders, INSERT OR IGNORE, returned ids."""
    out = sql.replace("%", "%%").replace("?", "%s")
    is_insert = re.match(r"\s*INSERT", out, flags=re.IGNORECASE) is not None
    if re.match(r"\s*INSERT OR IGNORE INTO", out, flags=re.IGNORECASE):
        out = re.sub(r"INSERT OR IGNORE INTO", "INSERT INTO", out, count=1, flags=re.IGNORECASE)
        out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    returning = is_insert and "RETURNING" not in out.upper()
    if returning:
        out = out.rstrip().rstrip(";") + " RETURNING id"
    return out, returning


class PgConnection:
    is_postgres = True

    def __init__(self, url):
        import psycopg

        # No server-side prepared statements, so connection poolers (Supabase, Neon) work.
        self._conn = psycopg.connect(url, row_factory=_row_factory, prepare_threshold=None)

    def execute(self, sql, params=()):
        translated, returning = translate(sql)
        cursor = self._conn.cursor()
        try:
            cursor.execute(translated, tuple(params))
        except Exception:
            self._conn.rollback()
            raise
        return PgCursor(cursor, returning)

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self._conn.execute(statement)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


LIBPQ_PARAMS = {"sslmode", "sslrootcert", "connect_timeout", "application_name", "options", "target_session_attrs"}


def clean_url(url):
    """Drop query parameters libpq does not know (Vercel's Supabase URLs add some)."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in LIBPQ_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def is_postgres_url(target):
    return str(target).startswith(("postgres://", "postgresql://"))


def connect(target):
    if is_postgres_url(target):
        return PgConnection(clean_url(str(target)))
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn):
    postgres = getattr(conn, "is_postgres", False)
    pk = "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY" if postgres else "INTEGER PRIMARY KEY"
    conn.executescript(SCHEMA.replace("{pk}", pk))
    for table, columns in MIGRATIONS.items():
        if postgres:
            for name, decl in columns.items():
                conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {decl}")
            continue
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS inbound_message_id ON inbound (message_id) "
        "WHERE message_id IS NOT NULL"
    )
    conn.commit()
