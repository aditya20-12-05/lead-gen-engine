"""Invitation drafts. The engine drafts; a person reviews, sends and marks sent.

Templates are fixed text with a few fields, so every draft is predictable and
checkable. An AI provider can be plugged in later to personalise drafts, but
its output passes through the same rules before anyone can mark it sent.
"""

WEBINAR_TITLE = "Coming Home: Planning your wealth, your return and your family's future"

TEMPLATES = {
    ("community", "en"): {
        "label": "Community body invitation (English, founder)",
        "subject": "A free online session for {org_name} members: planning your wealth and your return home",
        "body": """Dear Committee Members,

My name is {sender_name}, and I am the founder of SELEQT Private Wealth in Ahmedabad. Many families in our community will one day return to India, and I would like to offer {org_name} members a free online session titled "{title}".

The session covers:
1. Planning your wealth with the move in mind, across India and abroad, from today
2. Getting ready for the return: residency status, accounts, and how income and assets are treated
3. Succession planning: wills, nominations and clear records, in India and abroad
4. Passing wealth to the next generation, and the common mistakes to avoid

It is purely educational, about 45 minutes online from India followed by questions, with no sales content. If your committee is interested, I would be glad to fit a date and language (Gujarati or English) that suits your members. Whether to invite members is entirely your decision.

Warm regards,
{sender_name}
{sender_title}
{footer}
""",
        "needs_native_review": False,
    },
    ("community", "gu"): {
        "label": "Community body invitation (Gujarati, founder)",
        "subject": "{org_name} ના સભ્યો માટે નિઃશુલ્ક ઑનલાઇન સત્ર: સંપત્તિ આયોજન અને ઘર વાપસી",
        "body": """આદરણીય સમિતિ સભ્યો,

મારું નામ {sender_name} છે અને હું અમદાવાદ સ્થિત SELEQT Private Wealth નો સ્થાપક છું. આપણા સમાજના ઘણા પરિવારો એક દિવસ ભારત પરત ફરશે, અને હું {org_name} ના સભ્યો માટે "ઘર વાપસી: આપની સંપત્તિ, પરત ફરવાનું અને પરિવારના ભવિષ્યનું આયોજન" નામનું નિઃશુલ્ક ઑનલાઇન સત્ર યોજવા માંગુ છું.

સત્રમાં આ વિષયો આવરી લેવાશે:
1. પરત ફરવાને ધ્યાનમાં રાખીને આજથી ભારત અને વિદેશમાં સંપત્તિનું આયોજન
2. પરત ફરવાની તૈયારી: રહેઠાણ દરજ્જો, ખાતાં અને આવક તથા સંપત્તિ પર તેની અસર
3. વારસા આયોજન: ભારત અને વિદેશમાં વસિયતનામું, નોમિનેશન અને સ્પષ્ટ દસ્તાવેજો
4. આગામી પેઢીને સંપત્તિનું હસ્તાંતરણ અને સામાન્ય ભૂલોથી કેવી રીતે બચવું

આ સત્ર સંપૂર્ણપણે શૈક્ષણિક છે, ભારતથી આશરે 45 મિનિટ ઑનલાઇન યોજાશે અને પછી પ્રશ્નોત્તરી થશે; તેમાં કોઈ વેચાણ સામગ્રી નથી. જો આપની સમિતિને રસ હોય, તો આપના સભ્યોને અનુકૂળ તારીખ અને ભાષા (ગુજરાતી અથવા અંગ્રેજી) મુજબ હું આનંદથી આયોજન કરીશ. સભ્યોને આમંત્રણ આપવું કે નહીં તે સંપૂર્ણપણે આપનો નિર્ણય રહેશે.

સાદર,
{sender_name}
{sender_title}
{footer}
""",
        "needs_native_review": True,
    },
    ("employer", "en"): {
        "label": "Employer HR invitation (English, founder)",
        "subject": "A free financial wellbeing session for your Indian employees",
        "body": """Dear {org_name} HR Team,

My name is {sender_name}, and I am the founder of SELEQT Private Wealth in Ahmedabad. Many of your Indian colleagues will eventually return to India, and the financial side of that move raises the same questions every time: planning their wealth across two countries, residency status, succession, and passing wealth to their families.

I would like to offer your employees a free online session, "{title}". It is purely educational, delivered online from India, and contains no sales content. We can run it in English or Gujarati and adapt the length to your schedule.

If this would be useful as part of your employee wellbeing programme, I would be glad to find a suitable date.

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
    "sender_name": "[Founder name]",
    "sender_title": "Founder, SELEQT Private Wealth",
    "footer": "Ahmedabad, India",
}


BLANK = {
    "subject": "",
    "body": """[Write your email here]

Warm regards,
{sender_name}
{sender_title}
{footer}
""",
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


def render_blank(settings):
    fields = {**DEFAULT_SETTINGS, **settings}
    return BLANK["subject"], BLANK["body"].format(**fields)
