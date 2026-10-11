# SELEQT outreach engine

A web app for SELEQT's outreach to NRI communities. Outreach goes out in the
founder's voice (Ishit Lakhani) from ishit@seleqtwealth.in. The engine
organises, checks and tracks; a person reviews every message and sends it.
Nothing is sent on its own.

## How it is organised

**Country > approach > task.**

- **Country**: the UK, UAE, Qatar, Oman, Bahrain, Australia and so on.
- **Approach**: a channel in that country, with **our brief** for it.
  - UK: Weekly newspaper column (brief in `briefs/uk_newspaper_weekly_column.md`)
  - UAE, Qatar, Oman, Bahrain: Community webinars ("Coming Home: Planning your wealth, your return and your family's future")
  - Australia: Gujarati media interviews and columns (planned)
- **Task**: one organisation within an approach. The task page shows **them**
  (official email, phone or WhatsApp, website contact form, social page, their
  brief, source link and last source check) next to **us** (our brief, the
  plan for this organisation, the owner), then the conversation.

Contact works through any channel the organisation offers: email (sent and
replies caught from the engine, through Zoho), or website contact form,
WhatsApp, phone, social media message or in person (sent by a person and
recorded in the engine).

Other pages: Organisations (all targets and the source check), Webinars
(sessions and registrations), Enquiries (people who contacted SELEQT first),
Do not contact.

## Rules the engine enforces

| Rule | How |
|---|---|
| Permanent do-not-contact list | Checked before every draft, send, import and enquiry, by email, name and phone. The app has no way to delete entries. A reply asking to be removed puts the sender on the list automatically. Shared webmail domains cannot be blocked wholesale. |
| Nobody contacted twice | One first contact per organisation ever, on any channel, and one per email address across all approaches. Replies only after they have written back. No chasing. |
| A person sends | Email needs a ticked "I have read this email" box and a confirmation; other channels are sent by a person and recorded with who sent them. |
| Copy checks before sending | No em or en dashes, SELEQT always in capitals, no SEBI advertisement code red flags (assured returns, risk-free, superlatives), no unfilled `[placeholders]`; emails also need a subject. |
| Gulf: approach the community body only | The body decides whether to invite members. Registrants resident in the UAE, Qatar, Oman, Bahrain, Kuwait or Saudi Arabia get no follow-up; SELEQT replies only if they write first. |
| One follow-up at most elsewhere | Only with recorded consent, and only once. |
| RIA and MFD segregation | Each family (shared family key) is routed to one side only. |

## Data sources

The seeded organisations came from web search results gathered in October
2026; none of the source pages could be opened from the build environment, so
each starts as "not checked" until the source check runs. Shri Gujarati Samaj
Bahrain and SBS Gujarati have no contact route recorded yet.

Research behind the strategy is in `reports/` and `research_notes/`; briefs
for team members are in `briefs/`.
