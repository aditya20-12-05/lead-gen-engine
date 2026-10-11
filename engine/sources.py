"""Source health: fetch each organisation's source page and record what happened.

The result is stored as-is ("ok 200", "http 404", "error: ..."). Nothing is
inferred from a failure, and a reachable page does not prove the contact
details on it are still right; a person confirms those before sending.
"""

import urllib.error
import urllib.request

from .db import now

USER_AGENT = "Mozilla/5.0 (SELEQT source check)"


def check_url(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return f"ok {response.status}"
    except urllib.error.HTTPError as exc:
        return f"http {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return f"error: {reason}"


def check_all(conn, fetch=check_url):
    results = []
    for org in conn.execute("SELECT id, name, source_url FROM organisations ORDER BY id"):
        status = fetch(org["source_url"])
        conn.execute(
            "UPDATE organisations SET source_status = ?, source_checked_at = ? WHERE id = ?",
            (status, now(), org["id"]),
        )
        results.append((org["name"], org["source_url"], status))
    conn.commit()
    return results
