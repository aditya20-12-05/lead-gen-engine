"""Contact finder: read an organisation's own website for official contact routes.

Looks at the home page and up to four likely contact or about pages on the
same site, and collects email addresses, phone links, a contact form and
social media pages. Every finding keeps the page it was found on. Nothing is
applied automatically: a person accepts or ignores each suggestion.
"""

import re
import urllib.error
import urllib.parse
import urllib.request

from .db import now

USER_AGENT = "Mozilla/5.0 (SELEQT contact finder)"
MAX_PAGES = 5
CONTACT_HINTS = ("contact", "reach", "enquir", "connect", "about", "committee", "get-in-touch")
SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "youtube.com")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)""", re.IGNORECASE)
IGNORED_EMAIL_PARTS = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourname", "@2x", ".png", ".jpg", ".gif", ".svg", ".webp")


def fetch_page(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if "html" not in response.headers.get("Content-Type", "html"):
            return ""
        return response.read(2_000_000).decode("utf-8", errors="replace")


def _same_site(base, url):
    return urllib.parse.urlparse(base).netloc.lower().removeprefix("www.") == \
        urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def _clean_email(value):
    value = urllib.parse.unquote(value).split("?")[0].strip().strip(".").lower()
    if not EMAIL_RE.fullmatch(value) or any(part in value for part in IGNORED_EMAIL_PARTS):
        return None
    return value


def _clean_phone(value):
    value = urllib.parse.unquote(value).strip()
    digits = re.sub(r"\D", "", value)
    return value if 8 <= len(digits) <= 15 else None


def find_contacts(website, fetch=fetch_page):
    """Return (found, errors): found is a list of (kind, value, page_url)."""
    found, errors, seen = [], [], set()
    queue = [website]
    pages = 0
    while queue and pages < MAX_PAGES:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            errors.append(f"{url}: {getattr(exc, 'reason', exc)}")
            continue
        pages += 1
        links = [urllib.parse.urljoin(url, href.strip()) for href in HREF_RE.findall(page)]
        for link in links:
            lowered = link.lower()
            if lowered.startswith("mailto:"):
                email = _clean_email(link[7:])
                if email:
                    found.append(("email", email, url))
            elif lowered.startswith("tel:"):
                phone = _clean_phone(link[4:])
                if phone:
                    found.append(("phone", phone, url))
            elif any(host in urllib.parse.urlparse(lowered).netloc for host in SOCIAL_HOSTS):
                if not any(word in lowered for word in ("sharer", "share?", "intent/", "/plugins/")):
                    found.append(("social", link.rstrip("/"), url))
            elif _same_site(website, link) and any(hint in lowered for hint in CONTACT_HINTS):
                if link not in seen and link not in queue:
                    queue.append(link)
        for match in EMAIL_RE.findall(re.sub(r"<[^>]+>", " ", page)):
            email = _clean_email(match)
            if email:
                found.append(("email", email, url))
        if "contact" in url.lower() and "<form" in page.lower():
            found.append(("contact_form", url, url))
    unique, keys = [], set()
    for kind, value, page_url in found:
        if (kind, value) not in keys:
            keys.add((kind, value))
            unique.append((kind, value, page_url))
    return unique, errors


def run_for_org(conn, org, fetch=fetch_page):
    website = org["website"]
    if not website:
        return {"added": 0, "errors": ["No website recorded for this organisation."]}
    found, errors = find_contacts(website, fetch)
    added = 0
    for kind, value, page_url in found:
        cur = conn.execute(
            """INSERT OR IGNORE INTO contact_suggestions (org_id, kind, value, found_on, found_at)
               VALUES (?, ?, ?, ?, ?)""",
            (org["id"], kind, value, page_url, now()),
        )
        added += cur.rowcount
    conn.commit()
    return {"added": added, "errors": errors}


FIELD_FOR_KIND = {"email": "contact_email", "phone": "contact_phone",
                  "contact_form": "contact_form_url", "social": "social_url"}
