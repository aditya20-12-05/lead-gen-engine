# SELEQT outreach engine

A local web app for SELEQT's outreach to NRI communities, run from the
founder's laptop. All data stays in one SQLite file there, and the app is only
reachable from that computer (it listens on 127.0.0.1).

Outreach goes out in the founder's voice from ishit@seleqtwealth.in. The
engine organises, checks and tracks; a person reviews every email and presses
Send. Nothing is sent on its own.

## How it is organised

**Country > approach > task.**

- **Country**: the UK, UAE, Qatar, Oman, Bahrain, Australia and so on.
- **Approach**: a channel in that country, with **our brief** for it. Seeded:
  - UK: Weekly newspaper column (brief in `briefs/uk_newspaper_weekly_column.md`)
  - UAE, Qatar, Oman, Bahrain: Community webinars ("Coming Home: Planning your wealth, your return and your family's future")
  - Australia: Gujarati media interviews and columns (planned)
- **Task**: one organisation within an approach. The task page shows **them**
  (official email, their brief, source link and last source check) next to
  **us** (our brief, the plan for this organisation, the owner), then the email
  thread, with buttons to write, send and check for replies.

Other pages: Organisations (all targets and the source check), Webinars
(sessions and registrations), Enquiries (people who contacted SELEQT first),
Do not contact.

## Rules the engine enforces

| Rule | How |
|---|---|
| Permanent do-not-contact list | Checked before every draft, send, import and enquiry. The app has no way to delete entries. A reply asking to be removed puts the sender on the list automatically. Shared webmail domains cannot be blocked wholesale. |
| Nobody contacted twice | One first email per organisation and per email address, ever, across all approaches. Replies only after they have written back. No chasing. |
| A person sends | Send needs a ticked "I have read this email" box and a confirmation. |
| Copy checks before sending | No em or en dashes, SELEQT always in capitals, no SEBI advertisement code red flags (assured returns, risk-free, superlatives), no unfilled `[placeholders]`, a subject line. |
| Gulf: approach the community body only | The body decides whether to invite members. Registrants resident in the UAE, Qatar, Oman, Bahrain, Kuwait or Saudi Arabia get no follow-up; SELEQT replies only if they write first. |
| One follow-up at most elsewhere | Only with recorded consent, and only once. |
| RIA and MFD segregation | Each family (shared family key) is routed to one side only. |

## Setup on the laptop

Needs Python 3.10 or newer. Everything used is free.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
mkdir -p data && cp settings.example.json data/settings.json   # then put in the founder's name
.venv/bin/python -m engine seed                   # load countries, approaches and organisations
.venv/bin/python -m engine check-sources          # live health check of every source
.venv/bin/python -m engine serve                  # open http://127.0.0.1:5050
```

Run the tests with `.venv/bin/python -m pytest`.

## Connecting ishit@seleqtwealth.in

The engine sends through SMTP and reads replies through IMAP, so it works with
any mail provider that offers them. Create an **app password** in the mail
provider's security settings (do not use the normal login password), then set
these environment variables on the laptop before `serve`. They are never
written to a file in this repository.

```
export SELEQT_MAIL_USER=ishit@seleqtwealth.in
export SELEQT_MAIL_PASSWORD='the app password'
export SELEQT_SMTP_HOST=smtp.gmail.com     # Google Workspace; Zoho: smtp.zoho.in
export SELEQT_IMAP_HOST=imap.gmail.com     # Google Workspace; Zoho: imap.zoho.in
# optional: SELEQT_SMTP_PORT=587 for STARTTLS (default 465 SSL), SELEQT_IMAP_PORT (default 993)
# optional: SELEQT_IMAP_SENT='Sent' to file a copy of sent mail, for providers that do not do it themselves
```

The top bar shows "Mailbox: ishit@seleqtwealth.in" once connected. Reply
checks open the inbox read-only and never mark mail as read. Without the
mailbox connected, emails can still be copied out, sent personally, and
recorded as sent.

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
checked". Run `check-sources` on the laptop for the first real health report,
and confirm each email on the live page before sending.

No direct email is recorded yet for Muscat Gujarati Samaj, Shri Gujarati Samaj
Bahrain, Garavi Gujarat, Gujarat Samachar UK and Asian Voice, SBS Gujarati or
Namaskar Gujarat; their tasks show "needs email" until one is added.

Research behind the strategy is in `reports/` and `research_notes/`; briefs
for team members are in `briefs/`.
