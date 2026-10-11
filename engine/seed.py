"""Starting data: countries, approaches (with SELEQT's brief) and target organisations.

Every organisation row came from web search results gathered in October 2026;
none of the pages could be opened in full when the list was compiled. Run the
source check on the laptop and confirm each contact on the live page before
sending. Organisational contacts only.
"""

from .db import now

WEBINAR_BRIEF = """Coming Home: Planning your wealth, your return and your family's future

What it is about: most families living abroad plan to return home one day. The session helps them plan their overall wealth with that return in mind, so the move is smooth and the family is looked after along the way.

What it covers:
1. Planning wealth with the move in mind: savings and investments across India and abroad, from today
2. Getting ready for the return: residency status, accounts, how income and assets are treated
3. Succession planning: wills, nominations and clear records, in India and abroad
4. Passing wealth to the next generation: simple ways families plan transfers, and common mistakes

Format: about 45 minutes online from India, then questions. Purely educational, no sales content.

How we approach: email the community body only, from the founder. The body decides whether to invite its members. One email per body, no chasing. No follow-up marketing to Gulf attendees; reply only if they write first."""

UK_COLUMN_BRIEF = """# Brief: weekly column pitch to UK Gujarati newspapers

For the team member writing the email. Written in the founder's voice and sent
from ishit@seleqtwealth.in. One email per newspaper; no chasing if there is no
reply.

## Who it goes to
- Garavi Gujarat (Asian Media Group, London): weekly, Gujarati and English, readers include many business owners. Contact via amg.biz/contactus.php.
- Gujarat Samachar UK and Asian Voice (ABPL, London): weekly, Gujarati and English titles. Contact via abplgroup.com (Contact page).

## What we are asking for
- Start with one trial piece, so the editor can judge it with no commitment.
- Make clear that our real interest is a continued weekly series.

## What the column would cover
- Indian schemes and options available to NRIs, explained simply
- Wealth transfer and succession across India and the UK
- Planning the move back to India
- Other relevant Indian financial schemes and rules readers ask about

## Why the editor should care
- Practical topics their readers deal with: property and parents in India, inheritance, returning home.
- Free, written to their word count, deadlines and language (Gujarati or English).
- Steady weekly content from a family firm with deep roots (SELEQT Private Wealth, Ahmedabad; sister firm Lakhani Investments since 1987).

## Tone
Warm, respectful and short: a founder writing personally to an editor. Say we
believe the column would be genuinely attractive to their readers.

## Ask
- Would they like a trial piece?
- Who should it go to, and what word count and language do they prefer?

## Guardrails
- Educational only: no promotion of SELEQT's products or services, no return
  figures or promises. (UK rules treat promotion of investment services by a
  firm without FCA authorisation as a criminal offence.)
- "Schemes" means explaining rules and options in general, never recommending
  a specific fund or product.
- House style: no em or en dashes, SELEQT always in capitals."""

AU_BRIEF = """Offer free educational interviews and columns to Gujarati media in Australia on planning the move back to India, succession and wealth transfer.

Guardrails: educational only, no promotion of SELEQT's services and no paid ads (a foreign adviser must not set out to attract Australian clients without a local licence). One pitch per outlet, from the founder."""

ORGANISATIONS = [
    {
        "name": "Gujarati Samaj UAE", "kind": "community", "country": "AE", "city": "Dubai",
        "contact_email": "gujaratisamajemirates@gmail.com",
        "website": "https://gujaratisamajuae.ae/", "source_url": "https://gujaratisamajuae.ae/",
        "source_note": "Search snippets, Oct 2026. Claims 28,000+ members (self-reported). "
        "Publishes a monthly newsletter; runs the Vyapar Junction business network. "
        "A second site, gujaratisamajinuae.com, also appears; confirm which is current.",
    },
    {
        "name": "Gujarati Samaj Abu Dhabi", "kind": "community", "country": "AE", "city": "Abu Dhabi",
        "contact_email": "gujaratisamajabudhabi@yahoo.com",
        "website": "http://www.gujaratisamajabudhabi.com/",
        "source_url": "http://www.gujaratisamajabudhabi.com/aboutus.html",
        "source_note": "Search snippets, Oct 2026. Founded 1977, 400+ families, registered with "
        "the India Social and Cultural Centre. Site undated; 2025 to 2026 activity unconfirmed.",
    },
    {
        "name": "Gujarati Samaj Qatar", "kind": "community", "country": "QA", "city": "Doha",
        "contact_email": "gujarati.samaj.qatar@gmail.com",
        "website": "https://www.gsq.org.in/", "source_url": "https://www.gsq.org.in/",
        "source_note": "Search snippets, Oct 2026. Founded 2000; 2025 to 2026 committee listed; "
        "works under the Indian Cultural Centre.",
    },
    {
        "name": "Muscat Gujarati Samaj (Indian Social Club Oman)", "kind": "community", "country": "OM",
        "city": "Muscat", "contact_email": None,
        "social_url": "https://www.facebook.com/muscatgujaratisamajoman/",
        "website": "https://www.facebook.com/muscatgujaratisamajoman/",
        "source_url": "https://www.pressreader.com/oman/oman-daily-observer/20220404/281633898757603",
        "source_note": "Latest dated coverage April 2022 (45th anniversary). No public email found; "
        "reach it through the Indian Social Club Oman or its Facebook page.",
    },
    {
        "name": "Shri Gujarati Samaj Bahrain", "kind": "community", "country": "BH", "city": "Manama",
        "contact_email": None, "website": None,
        "source_url": "https://bi50.bahrainthismonth.com/shri-gujarati-samaj/",
        "source_note": "Formed 1980; about 800 paid members (sources conflict). No public email found.",
    },
    {
        "name": "Garavi Gujarat (Asian Media Group)", "kind": "media", "country": "GB", "city": "London",
        "contact_email": None, "contact_form_url": "https://www.amg.biz/contactus.php",
        "website": "https://www.garavigujarat.biz/",
        "source_url": "https://www.garavigujarat.biz/about-us/",
        "source_note": "Weekly since 1968, Gujarati and English. About 60,000 copies a week "
        "(ad brokers, undated); the group claims 1.3 million monthly readers across all titles. "
        "Same publisher as Eastern Eye, Asian Trader and Asian Hospitality. No editor email found; "
        "use the contact form at amg.biz/contactus.php or ask for the editorial address.",
    },
    {
        "name": "Gujarat Samachar UK and Asian Voice (ABPL)", "kind": "media", "country": "GB",
        "city": "London", "contact_email": None, "contact_phone": "+44 20 7749 4080",
        "website": "https://www.abplgroup.com/",
        "source_url": "https://www.abplgroup.com/",
        "source_note": "Gujarat Samachar UK, weekly since 1972 (Gujarati), and its English sister "
        "Asian Voice; founder and editor CB Patel. Claims 200,000+ weekly readers; Wikipedia cites "
        "about 25,000 copies. Contact page on abplgroup.com, phone +44 20 7749 4080.",
    },
    {
        "name": "SBS Gujarati", "kind": "media", "country": "AU", "city": "Sydney",
        "contact_email": None, "website": "https://www.sbs.com.au/language/gujarati",
        "source_url": "https://www.sbs.com.au/language/gujarati",
        "source_note": "Public broadcaster's Gujarati radio and podcast, episodes confirmed Feb to "
        "May 2026. No paid content; pitch an expert interview. No audience figure published.",
    },
    {
        "name": "Namaskar Gujarat", "kind": "media", "country": "AU", "city": "Brisbane",
        "contact_email": None, "social_url": "https://x.com/NamaskarGujarat",
        "website": "https://namaskargujarat.com",
        "source_url": "https://namaskargujarat.com",
        "source_note": "Calls itself Australia's only Gujarati newspaper; free print and e-paper "
        "in six cities. Latest issue seen April 2023, web headline July 2025; 2026 activity unconfirmed.",
    },
]

# Dates from web search results, October 2026; festival dates follow the Hindu
# calendar, so confirm against a panchang before planning around them.
CALENDAR = [
    ("2026-10-11", "2026-10-20", "Navratri", "festival", None,
     "Peak season for Gujarati Samaj events abroad (garba, dandiya)."),
    ("2026-10-20", None, "Dussehra", "festival", None, None),
    ("2026-11-08", None, "Diwali", "festival", None, "Community bodies hold Diwali events; avoid sending on the day."),
    ("2026-12-15", "2027-01-31", "NRI winter visit season (approximate)", "season", None,
     "Many NRIs visit Gujarat for weddings and festivals."),
    ("2027-01-09", None, "Pravasi Bharatiya Divas", "festival", None, "Observed every year on 9 January."),
    ("2027-01-10", "2027-01-12", "Vibrant Gujarat Global Summit, Gandhinagar", "festival", None,
     "11th edition; NRG delegates attend."),
    ("2027-01-14", None, "Uttarayan", "festival", None, None),
]

APPROACHES = [
    {"country": "AE", "name": "Community webinars", "template_kind": "community", "status": "active",
     "brief": WEBINAR_BRIEF, "orgs": ["Gujarati Samaj UAE", "Gujarati Samaj Abu Dhabi"]},
    {"country": "QA", "name": "Community webinars", "template_kind": "community", "status": "active",
     "brief": WEBINAR_BRIEF, "orgs": ["Gujarati Samaj Qatar"]},
    {"country": "OM", "name": "Community webinars", "template_kind": "community", "status": "active",
     "brief": WEBINAR_BRIEF, "orgs": ["Muscat Gujarati Samaj (Indian Social Club Oman)"]},
    {"country": "BH", "name": "Community webinars", "template_kind": "community", "status": "active",
     "brief": WEBINAR_BRIEF, "orgs": ["Shri Gujarati Samaj Bahrain"]},
    {"country": "GB", "name": "Weekly newspaper column", "template_kind": None, "status": "active",
     "brief": UK_COLUMN_BRIEF,
     "orgs": ["Garavi Gujarat (Asian Media Group)", "Gujarat Samachar UK and Asian Voice (ABPL)"]},
    {"country": "AU", "name": "Gujarati media interviews and columns", "template_kind": None,
     "status": "planned", "brief": AU_BRIEF, "orgs": ["SBS Gujarati", "Namaskar Gujarat"]},
]


# Contacts found after the first seed. Applied once per CONTACTS_VERSION to new
# and existing databases. A field is only written when it is empty, or still
# holds the value we seeded before ("was"), so edits made on the site are kept.
CONTACTS_VERSION = "1"
CONTACT_UPDATES = []

CONTACT_FIELDS = ("contact_email", "contact_phone", "contact_form_url", "social_url", "website")


def apply_contact_updates(conn):
    row = conn.execute("SELECT value FROM meta WHERE key = 'contacts_version'").fetchone()
    if row and row[0] == CONTACTS_VERSION:
        return 0
    changed = 0
    for update in CONTACT_UPDATES:
        org = conn.execute(
            "SELECT * FROM organisations WHERE name = ? AND country = ?", (update["name"], update["country"])
        ).fetchone()
        if org is None:
            continue
        was = update.get("was", {})
        for field in CONTACT_FIELDS:
            value = update.get(field)
            current = org[field]
            if value and value != current and (not current or current == was.get(field)):
                conn.execute(f"UPDATE organisations SET {field} = ? WHERE id = ?", (value, org["id"]))
                changed += 1
        note = update.get("note")
        if note and note not in (org["source_note"] or ""):
            joined = ((org["source_note"] or "").rstrip() + "\n\n" + note).strip()
            conn.execute("UPDATE organisations SET source_note = ? WHERE id = ?", (joined, org["id"]))
    conn.execute("DELETE FROM meta WHERE key = 'contacts_version'")
    conn.execute("INSERT INTO meta (key, value) VALUES ('contacts_version', ?)", (CONTACTS_VERSION,))
    conn.commit()
    return changed


def _brief(approach):
    return approach["brief"]


def seed(conn):
    added = 0
    for org in ORGANISATIONS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO organisations
               (name, kind, country, city, contact_email, contact_phone, contact_form_url, social_url,
                website, source_url, source_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (org["name"], org["kind"], org["country"], org["city"], org["contact_email"],
             org.get("contact_phone"), org.get("contact_form_url"), org.get("social_url"),
             org["website"], org["source_url"], org["source_note"], now()),
        )
        added += cur.rowcount
    for approach in APPROACHES:
        conn.execute(
            """INSERT OR IGNORE INTO approaches (country, name, our_brief, template_kind, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (approach["country"], approach["name"], _brief(approach), approach["template_kind"],
             approach["status"], now()),
        )
        approach_id = conn.execute(
            "SELECT id FROM approaches WHERE country = ? AND name = ?", (approach["country"], approach["name"])
        ).fetchone()["id"]
        for org_name in approach["orgs"]:
            org_id = conn.execute(
                "SELECT id FROM organisations WHERE name = ? AND country = ?", (org_name, approach["country"])
            ).fetchone()["id"]
            conn.execute(
                "INSERT OR IGNORE INTO tasks (approach_id, org_id, created_at) VALUES (?, ?, ?)",
                (approach_id, org_id, now()),
            )
    for date, end_date, title, kind, country, note in CALENDAR:
        conn.execute(
            """INSERT OR IGNORE INTO calendar_items (date, end_date, title, kind, country, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, end_date, title, kind, country, note, now()),
        )
    conn.commit()
    return added
