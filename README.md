# SELEQT outreach engine

A local web app for SELEQT's educational webinar programme. It runs on the
wealth manager's laptop, keeps all data in one SQLite file there, and is only
reachable from that computer (it listens on 127.0.0.1).

The engine finds, drafts, checks and tracks. A person sends every message from
the official mailbox and records it. Nothing is sent automatically, on any
channel.

## What it does

- **Organisations**: community bodies, employers (HR teams) and media. Each
  entry carries the source URL its details came from. Seeded with the Gulf
  Gujarati community bodies (organisational contacts only).
- **Source health**: fetches every source page and stores exactly what
  happened (`ok 200`, `http 404`, `error: ...`). A reachable page does not prove
  the contact is still right; confirm it on the live page before sending.
- **Invitation drafts**: fixed templates in English and Gujarati for community
  bodies, and English for employer HR teams. The webinar is "Coming Home:
  Planning your return to India, your wealth and your family's succession".
  The Gujarati draft is flagged for native-speaker review.
- **Copy checks** before anything can be marked sent: no em or en dashes,
  SELEQT always in capitals, no SEBI advertisement code red flags (assured
  returns, risk-free, superlatives), no unfilled `[placeholders]`.
- **Webinars and registrations**: schedule sessions, import registrations from
  a CSV (for example a Google Forms export) with the consent wording each
  person agreed to.
- **Enquiries**: only people who contacted SELEQT first, with their first
  message kept word for word as evidence.

## Rules the engine enforces

| Rule | How |
|---|---|
| Permanent do-not-contact list | Checked before every draft, send, import and enquiry. The app has no way to delete entries. Shared webmail domains cannot be blocked wholesale. |
| Nobody contacted twice | One invitation per organisation and per email address, ever. Replies only after the organisation has written back. |
| Gulf: approach the community body only | Invitations go to the body; it decides whether to invite members. Registrants resident in the UAE, Qatar, Oman, Bahrain, Kuwait or Saudi Arabia get no follow-up; SELEQT replies only if they write first. |
| One follow-up at most elsewhere | Only with recorded consent, and only once. |
| RIA and MFD segregation | Each family (shared family key) is routed to one side only. |
| Human sends | Drafts are copied into the official mailbox by a person, who then records who sent it. |

## Setup on the laptop

Needs Python 3.10 or newer. Everything used is free.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
mkdir -p data && cp settings.example.json data/settings.json   # then edit sender name and title
.venv/bin/python -m engine seed                   # load the Gulf community bodies
.venv/bin/python -m engine check-sources          # live health check of every source
.venv/bin/python -m engine serve                  # open http://127.0.0.1:5050
```

Run the tests with `.venv/bin/python -m pytest`.

## Registration form (free, Google Forms)

Fields: name, email, country of residence (two-letter code), and two consent
statements, stored word for word:

1. Required: "I agree that SELEQT may use my name and email to send me the
   joining details and recording for this session."
2. Optional: "I agree that SELEQT may send me one follow-up email about this
   session." (export as `yes` or `no` in `consent_followup`)

Export the responses as CSV with the columns `name, email, country,
consent_followup, consent_text` and import them on the webinar's page.

## Data sources and their health

The seeded organisations came from web search results gathered in October
2026. None of the source pages could be opened from the build environment
(its network policy blocks those sites), so every entry starts as "not
checked". Run `check-sources` on the laptop for the first real health report.
Muscat Gujarati Samaj and Shri Gujarati Samaj Bahrain have no public email, so
drafting is blocked for them until an official address is recorded.

Research behind the strategy is in `reports/` and `research_notes/`.

## Not included yet

- An AI provider for personalised drafts (waiting for the provider and key;
  the key goes in an environment variable, never in the repository).
- Employer and UK, Africa and Australia organisation lists.
