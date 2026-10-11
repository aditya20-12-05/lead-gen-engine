"""Invitation drafts. The engine drafts; a person reviews, sends and marks sent.

Templates are fixed text with a few fields, so every draft is predictable and
checkable. An AI provider can be plugged in later to personalise drafts, but
its output passes through the same rules before anyone can mark it sent.
"""

WEBINAR_TITLE = "Coming Home: Planning your return to India, your wealth and your family's succession"

TEMPLATES = {
    ("community", "en"): {
        "label": "Community body invitation (English)",
        "subject": "A free online session for {org_name} members: planning the move back to India",
        "body": """Dear Committee Members,

Many families in our community will one day return to India. SELEQT would like to offer {org_name} members a free online session titled "{title}".

The session covers:
1. Residency status on return (NRI, RNOR and resident) and why timing matters
2. What happens to NRE, NRO and FCNR accounts and to assets held abroad
3. General principles for planning your wealth from now on
4. Succession: wills, nominations and legal heirs in India and abroad

It is purely educational, held online from India, and includes no sales content. If your committee is interested, we would be glad to fit a date and language (Gujarati or English) that suits your members. Whether to invite members is entirely your decision.

Warm regards,
{sender_name}
{sender_title}
{footer}
""",
        "needs_native_review": False,
    },
    ("community", "gu"): {
        "label": "Community body invitation (Gujarati)",
        "subject": "{org_name} ના સભ્યો માટે નિઃશુલ્ક ઑનલાઇન સત્ર: ભારત પરત ફરવાનું આયોજન",
        "body": """આદરણીય સમિતિ સભ્યો,

આપણા સમાજના ઘણા પરિવારો એક દિવસ ભારત પરત ફરશે. SELEQT {org_name} ના સભ્યો માટે "ઘર વાપસી: ભારત પરત ફરવાનું, સંપત્તિનું અને પરિવારના વારસાનું આયોજન" નામનું નિઃશુલ્ક ઑનલાઇન સત્ર યોજવા માંગે છે.

સત્રમાં આ વિષયો આવરી લેવાશે:
1. પરત ફર્યા પછીનો રહેઠાણ દરજ્જો (NRI, RNOR અને રહેવાસી) અને સમયનું મહત્વ
2. NRE, NRO અને FCNR ખાતાં તથા વિદેશમાં રહેલી સંપત્તિનું શું થાય છે
3. હવેથી સંપત્તિના આયોજનના સામાન્ય સિદ્ધાંતો
4. વારસા આયોજન: ભારત અને વિદેશમાં વસિયતનામું, નોમિનેશન અને કાયદેસર વારસદાર

આ સત્ર સંપૂર્ણપણે શૈક્ષણિક છે, ભારતથી ઑનલાઇન યોજાશે અને તેમાં કોઈ વેચાણ સામગ્રી નથી. જો આપની સમિતિને રસ હોય, તો આપના સભ્યોને અનુકૂળ તારીખ અને ભાષા (ગુજરાતી અથવા અંગ્રેજી) મુજબ અમે આનંદથી આયોજન કરીશું. સભ્યોને આમંત્રણ આપવું કે નહીં તે સંપૂર્ણપણે આપનો નિર્ણય રહેશે.

સાદર,
{sender_name}
{sender_title}
{footer}
""",
        "needs_native_review": True,
    },
    ("employer", "en"): {
        "label": "Employer HR invitation (English)",
        "subject": "A free financial wellbeing session for your Indian employees",
        "body": """Dear {org_name} HR Team,

Many of your Indian colleagues will eventually return to India, and the financial side of that move raises the same questions every time: residency status and tax, what happens to Indian and overseas accounts, long term planning, and succession for their families.

SELEQT would like to offer your employees a free online session, "{title}". It is purely educational, delivered online from India, and contains no sales content. We can run it in English or Gujarati and adapt the length to your schedule.

If this would be useful as part of your employee wellbeing programme, we would be glad to find a suitable date.

Kind regards,
{sender_name}
{sender_title}
{footer}
""",
        "needs_native_review": False,
    },
}

REPLY_SCAFFOLD = {
    "subject": "Re: {last_subject}",
    "body": """Dear {org_name} team,

[Write your reply here]

Warm regards,
{sender_name}
{sender_title}
{footer}
""",
}

DEFAULT_SETTINGS = {
    "sender_name": "[Sender name]",
    "sender_title": "[Sender title]",
    "footer": "SELEQT Private Wealth, Ahmedabad, India",
}


def templates_for(kind):
    return {lang: t for (k, lang), t in TEMPLATES.items() if k == kind}


def render_invite(org, language, settings):
    template = TEMPLATES.get((org["kind"], language))
    if template is None:
        raise KeyError(f"No {language} invitation template for {org['kind']} organisations.")
    fields = {**DEFAULT_SETTINGS, **settings, "org_name": org["name"], "title": WEBINAR_TITLE}
    return template["subject"].format(**fields), template["body"].format(**fields)


def render_reply(org, last_subject, settings):
    fields = {**DEFAULT_SETTINGS, **settings, "org_name": org["name"], "last_subject": last_subject}
    return REPLY_SCAFFOLD["subject"].format(**fields), REPLY_SCAFFOLD["body"].format(**fields)
