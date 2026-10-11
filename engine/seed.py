"""Starting list: Gulf Gujarati community bodies, organisational contacts only.

Every row came from web search results gathered in October 2026; none of the
pages could be opened in full when the list was compiled. Run the source check
on the laptop and confirm each contact on the live page before sending.
"""

from .db import now

GULF_COMMUNITY_BODIES = [
    {
        "name": "Gujarati Samaj UAE",
        "country": "AE",
        "city": "Dubai",
        "contact_email": "gujaratisamajemirates@gmail.com",
        "website": "https://gujaratisamajuae.ae/",
        "source_url": "https://gujaratisamajuae.ae/",
        "source_note": "Search snippets, Oct 2026. Claims 28,000+ members (self-reported). "
        "Publishes a monthly newsletter; runs the Vyapar Junction business network. "
        "A second site, gujaratisamajinuae.com, also appears; confirm which is current.",
    },
    {
        "name": "Gujarati Samaj Abu Dhabi",
        "country": "AE",
        "city": "Abu Dhabi",
        "contact_email": "gujaratisamajabudhabi@yahoo.com",
        "website": "http://www.gujaratisamajabudhabi.com/",
        "source_url": "http://www.gujaratisamajabudhabi.com/aboutus.html",
        "source_note": "Search snippets, Oct 2026. Founded 1977, 400+ families, registered with "
        "the India Social and Cultural Centre. Site undated; 2025 to 2026 activity unconfirmed.",
    },
    {
        "name": "Gujarati Samaj Qatar",
        "country": "QA",
        "city": "Doha",
        "contact_email": "gujarati.samaj.qatar@gmail.com",
        "website": "https://www.gsq.org.in/",
        "source_url": "https://www.gsq.org.in/",
        "source_note": "Search snippets, Oct 2026. Founded 2000; 2025 to 2026 committee listed; "
        "works under the Indian Cultural Centre.",
    },
    {
        "name": "Muscat Gujarati Samaj (Indian Social Club Oman)",
        "country": "OM",
        "city": "Muscat",
        "contact_email": None,
        "website": "https://www.facebook.com/muscatgujaratisamajoman/",
        "source_url": "https://www.pressreader.com/oman/oman-daily-observer/20220404/281633898757603",
        "source_note": "Latest dated coverage April 2022 (45th anniversary). No public email found; "
        "reach it through the Indian Social Club Oman or its Facebook page.",
    },
    {
        "name": "Shri Gujarati Samaj Bahrain",
        "country": "BH",
        "city": "Manama",
        "contact_email": None,
        "website": None,
        "source_url": "https://bi50.bahrainthismonth.com/shri-gujarati-samaj/",
        "source_note": "Formed 1980; about 800 paid members (sources conflict). No public email found.",
    },
]


def seed(conn):
    added = 0
    for org in GULF_COMMUNITY_BODIES:
        cur = conn.execute(
            """INSERT OR IGNORE INTO organisations
               (name, kind, country, city, contact_email, website, source_url, source_note, created_at)
               VALUES (?, 'community', ?, ?, ?, ?, ?, ?, ?)""",
            (
                org["name"],
                org["country"],
                org["city"],
                org["contact_email"],
                org["website"],
                org["source_url"],
                org["source_note"],
                now(),
            ),
        )
        added += cur.rowcount
    conn.commit()
    return added
