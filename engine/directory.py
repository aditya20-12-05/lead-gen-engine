"""Gujarati community bodies from the International Gujarati Samaj directory.

Source: a PDF list shared by SELEQT (undated, and some entries look many years
old). Entries listed twice are merged. Where the listed country contradicts
the address (for example a Fremont, California body filed under Australia), the
address wins and the note says so. Phone numbers are as listed; contacts may be
out of date, so confirm before sending.

Applied once per DIRECTORY_VERSION to new and existing databases. Each body is
added to its country's "Community webinars" approach, which is created with the
webinar brief if the country does not have one yet. Bodies already in the engine
only have empty fields filled and the directory details added to their notes.
"""

from .db import now

DIRECTORY_VERSION = "1"
SOURCE = "International Gujarati Samaj directory (PDF shared by SELEQT)"
CAVEAT = ("From the International Gujarati Samaj directory shared by SELEQT. The list is undated and some "
          "entries look old, so confirm the contact before sending.")

COMMUNITY_BRIEF = """Coming Home: Planning your wealth, your return and your family's future

What it is about: most families living abroad plan to return home one day. The session helps them plan their overall wealth with that return in mind, so the move is smooth and the family is looked after along the way.

What it covers:
1. Planning wealth with the move in mind: savings and investments across India and abroad, from today
2. Getting ready for the return: residency status, accounts, how income and assets are treated
3. Succession planning: wills, nominations and clear records, in India and abroad
4. Passing wealth to the next generation: simple ways families plan transfers, and common mistakes

Format: about 45 minutes online from India, then questions. Purely educational, no sales content.

How we approach: email the community body only, from the founder. The body decides whether to invite its members. One email per body, no chasing.

Guardrails: educational only, no promotion of SELEQT's products or services and no return figures (local rules on promoting financial services without a local licence)."""

# name, country, city, email, phone, address, extra note
D = [
    # Australia
    ("Gujarati Samaj of Western Australia", "AU", "Perth", None, "0448 791 436",
     "PO Box 351, Tuart Hill, WA 6939", "Contacts: Jignesh Shah 0448 791 436, Virendra Parikh 0412 052 304."),
    ("Gujarati Samaj New South Wales", "AU", "Sydney", "president@gujaratisamaj.org.au", "0433 195 430",
     None, "President: Jaydatt Nayak, mobile 0433 195 430."),
    ("Gujarati Mitra Mandal", "AU", "Melbourne", "svkhatri@yahoo.com", None,
     "3 Queenferry Place, Greenvale, Victoria", None),
    ("Gujarati Association of Victoria", "AU", "Melbourne", None, None, "PO Box 497, Reservoir, Victoria", None),
    ("Gujarati Association of Queensland", "AU", "Brisbane", None, "0415 251 748",
     "Kenmore Library, Kenmore Village, 9 Brookfield Road, Kenmore 4069", None),
    ("Gujarati Association of Australia", "AU", "Sydney", "info@yuvagujarat.com.au", None,
     "Unit 4, 60 Wigram Street, Harris Park, NSW 2150", None),
    # Canada
    ("Arya Samaj Ottawa", "CA", "Ottawa", None, "+1 613 738 2752", "149 Sai Crescent, Ottawa, Ontario", None),
    ("Gujarati Mandal of Calgary", "CA", "Calgary", "info@gujaratimandalcalgary.ca", None,
     "PO Box 1003 Stn M, Calgary, Alberta", None),
    ("Gujarati Samaj of Montreal", "CA", "Montreal", "info@gujaratisamaj.ca", None,
     "PO Box 38120, 3347 Boulevard des Sources, Dollard-des-Ormeaux, Quebec",
     "Listed twice (also as Gujarati Samaj Montreal Inc)."),
    ("Gujarati Cultural Society of Toronto", "CA", "Toronto", None, None, "134 Rimmington Drive, Thornhill, Ontario", None),
    ("Jain Society of Alberta", "CA", "Edmonton", "mukesh.khimasia@gmail.com", "+1 780 435 9070",
     "14225 133 Avenue, Edmonton, Alberta T5L 4W3", None),
    ("Gujarati Society of British Columbia", "CA", "Vancouver", "news@gsbc.ca", "+1 604 523 9360",
     "PO Box 4224, Main PO, Vancouver, BC V6B 3Z7", "Contact: Sureshbhai Desai."),
    ("Garvi Gujarat Association of Canada", "CA", "Edmonton", "garvigujaratedmonton@gmail.com", None,
     "Upper floor, Maharaja Banquet Hall, 9257 34 Avenue, Edmonton, Alberta T6E 5T5", None),
    ("Gujarat Samaj of Ontario", "CA", "Toronto", None, None, "14 Upton Crescent, Markham, Ontario", None),
    ("Halton Gujarati Samaj", "CA", "Milton", "haltongujaratisamaj@gmail.com", "+1 416 436 2537",
     "982 Farmstead Drive, Milton, ON L9T 8J1", "President: Nik (Niraj) Thakkar."),
    ("Brahmin Samaj (Society) of Ontario", "CA", "Brampton", "brahmin.samaj@yahoo.ca", None,
     "116-10 Gillingham Drive, Suite 478, Brampton, ON L6X 5A5", None),
    ("Alberta Gujarati Association", "CA", "Edmonton", "alberta.gujarati.association@gmail.com", None,
     "#207, 4918 Roper Road, Edmonton, AB T6B 3T7", None),
    ("Gujarati Cultural Society of Manitoba", "CA", "Winnipeg", "info@gcsm.org", None,
     "103-86 Niakwa Road, Winnipeg, MB R2M 3A9", None),
    ("The Gujarati Samaj of Regina", "CA", "Regina", "president@reginagujaratisamaj.com", None,
     "PO Box 4153, Regina, SK S4P 3W5", None),
    # UAE
    ("Gujarati Samaj Dubai", "AE", "Dubai", "admin@gujaratisamajdubai.com", "+971 4 335 6590", "PO Box 3103, Dubai",
     "A separate, older body from Gujarati Samaj UAE. President J R Hadani; Vice President Lina Dalal "
     "050 482 7120; Secretary Jaydeep Malkan 04 807 9265."),
    # Germany
    ("Gujarati Samaj Germany e.V.", "DE", "Frankfurt", "info@gujaratisamajgermany.com", None,
     "Heidestrasse 34, 60316 Frankfurt", "Contact: Himansu Patel."),
    ("Jain Association International (Germany) e.V.", "DE", "Henstedt-Ulzburg", "ajitkbenadi@onlinehome.de",
     "+49 4193 968360", "Schweriner Str. 5, 24558 Henstedt-Ulzburg",
     "President Ajit Benadi; Vice President Friedrich Wolff."),
    # Hong Kong
    ("Gujarati Samaj Hong Kong", "HK", "Hong Kong", "dk.patel@lgt.com", "+852 2523 6180",
     "GPO Box 8765, Room 2908, Two Exchange Square, 8 Connaught Place, Central",
     "The email is a named person's work address (D K Patel), not the Samaj's own."),
    ("The Gujarat Samaj Ltd", "HK", "Hong Kong", "info@gujaratsamajhk.com", None,
     "Unit C and D, 11/F, Centre Mark II, 305 to 313 Queen's Road Central", None),
    # Kenya (Nairobi numbers are listed in the old +254 2 format; the city code is now +254 20)
    ("Visa Oshwal Community", "KE", "Nairobi", None, "+254 2 553161", "PO Box 18492, Nairobi", None),
    ("Shri Kathiawar Jansari Mandal", "KE", "Nairobi", None, "+254 2 220753", "PO Box 40839, Nairobi", None),
    ("Patel Brotherhood (Nairobi)", "KE", "Nairobi", None, "+254 2 557227", "PO Box 18408, Nairobi", None),
    ("Shri Gurjar Sutar Community", "KE", "Nairobi", None, "+254 2 558187", "PO Box 46367, Nairobi", None),
    ("Shri Cutchi Madhapur P.G.M.", "KE", "Nairobi", None, "+254 2 822748", "PO Box 46768, Nairobi", None),
    ("Kenya Brahma Sabha", "KE", "Nairobi", None, "+254 2 338984", "PO Box 48385, Nairobi", None),
    ("Kenya Pragati Mandal", "KE", "Nairobi", None, "+254 2 223551", "PO Box 42796, Nairobi", None),
    ("Kenya India Friendship Association", "KE", "Nairobi", "cmake@arcc.or.ke", "226225 / 221910",
     "PO Box 74800, Nairobi", None),
    ("Lohana Mahajan Mandal (Nairobi)", "KE", "Nairobi", None, "+254 2 229091", "PO Box 43376, Nairobi", None),
    ("Arya Samaj Nairobi", "KE", "Nairobi", None, "+254 2 443553", "PO Box 14535, Nairobi", None),
    ("Gujarati Samaj, Limbachia Val (Mombasa)", "KE", "Mombasa", None, None, "Box 81172, Mombasa",
     "Listed under South Africa as Gujarati Samaj of South Africa, but the address is in Mombasa, Kenya."),
    # Malaysia
    ("Gujarati Association Wilayah Persekutuan and Selangor", "MY", "Kuala Lumpur", "info@gujaratikl.com.my", None,
     "No. 38, Lorong Maarof, Bangsar Park, Bangsar, 59100 Kuala Lumpur", None),
    # Mauritius
    ("Arya Sabha Mauritius", "MU", "Port Louis", "info@aryasabhamauritius.mu", "+230 208 5704",
     "1 Maharshi Dayanand St, Champ de Mars, Port Louis", "Also +230 212 2730."),
    # New Zealand
    ("Gujarati Samaj New Zealand", "NZ", "Auckland", "info@gujaratisamajnz.com", "+64 9 551 4519",
     "45/47 New Windsor Road, Avondale, Auckland 0600", None),
    ("New Zealand Jain Sangh", "NZ", "Auckland", "info@nzjainsangh.org", "+64 9 825 0375",
     "44F Portage Road, New Lynn, Auckland", None),
    # Singapore
    ("Singapore Gujarati Society", "SG", "Singapore", "admin@sgs.org.sg", "+65 6396 0900",
     "Gujarati Bhavan, 13 Cuff Road, Singapore 209724", None),
    ("Singapore Gujarati School", "SG", "Singapore", "admin@sgsl.org.sg", "+65 6345 2257",
     "225 Joo Chiat Road, Singapore 427488", None),
    # South Africa
    ("The Transvaal United Patidar Society", "ZA", "Johannesburg", "devland@jumbo.co.za", None,
     "PO Box 86016, City Deep 2049, Transvaal", "Phone listed as 21 11 8347732, which looks garbled (South Africa is +27)."),
    # Tanzania
    ("Patel Brotherhood, Patel Samaj (Dar es Salaam)", "TZ", "Dar es Salaam", "harishpatel_54@yahoo.com",
     "0713 618 956", "PO Box 1134, Dar es Salaam", None),
    ("Shree Lohana Mahajan (Dar es Salaam)", "TZ", "Dar es Salaam", "generalsecretary@lohanatz.com", "0784 216 216",
     "PO Box 1313, Dar es Salaam", None),
    ("Shree Patel Samaj (Mwanza)", "TZ", "Mwanza", "avee82@hotmail.com", "0754 436 890", "PO Box 1645, Mwanza",
     "Also 2541055 / 2551596."),
    ("Shree Jain Sangh (Dar es Salaam)", "TZ", "Dar es Salaam", "premium@cats-net.com", "0713 306 930",
     "PO Box 3016, Dar es Salaam", "Also 2117693."),
    # Thailand
    ("Gujarati-Marwari Society", "TH", "Bangkok", None, "02 223 1166",
     "6th floor, Mahatun Plaza, 888/160-5 Ploenchit Road, Lumpini, Pathumwan, Bangkok 10330", "Also 02 223 7290."),
    ("Arya Samaj Bangkok", "TH", "Bangkok", None, "+66 2 212 0907", "9 Don Kusol Soi 3, Yannawa, Bangkok", None),
    # UK
    ("Aden Vanik Association of UK", "GB", "Watford", None, "01923 893421",
     "9 Cedarwood Drive, Garston, Watford WD2 6RR", "Listed as Jain Organizations in United Kingdom."),
    ("Shree Kadwa Patidar Samaj (UK)", "GB", "Harrow", "secretary@kpsuk.org", "020 8909 2711",
     "Kenmore Avenue, Harrow, Middlesex HA3 8LU", None),
    ("Jain Samaj Europe", "GB", "Leicester", "help@jaincentre.com", "0116 254 1150",
     "Jain Centre, 32 Oxford Street, Leicester LE1 5XU", "Listed twice; also 0116 254 3091."),
    ("Vishwa Gujarati Samaj UK", "GB", "Harrow", "jdrdave@aol.com", "020 8863 2376",
     "93A Harrow View, Harrow HA1 4SZ", "Contact: Jagdish Dave."),
    ("Lohana Community of the United Kingdom", "GB", "Ilford", "secretary@lcuk.org.uk", None,
     "PO Box 2209, Ilford, Essex IG1 9TH", None),
    ("Shree Ram Mandir, Lohana Mahajan Leicester", "GB", "Leicester", "info@rammandirleicester.org.uk", "0116 266 4642",
     "Nitiben Maheshbhai Gheewala Centre, Hildyard Road, Leicester LE4 5GG", None),
    ("Lohana Mahajan Southampton", "GB", "Southampton", None, "023 8090 4317",
     "38 Mowbray Road, Sholing, Southampton SO19 8GN", "Also 023 8036 2907."),
    ("Gujarat Samaj Nottingham", "GB", "Nottingham", "gujaratsamaj@hotmail.com", "07581 422396",
     "28 Handel Street, Nottingham NG3 1JE",
     "Association of Gujarati Speaking People of Nottingham and Nottinghamshire. Also Himanshu Thakor 07837 530028."),
    ("Gujarati Association (Wolverhampton)", "GB", "Wolverhampton", "info@gujaratiassociation.org.uk", "07580 329943",
     "Mander Street, off Upper Zoar St, Pennfields, Wolverhampton WV3 0JZ", None),
    ("Shree Kutch Leva Patel Community (UK)", "GB", "Northolt", "info@sklpc.com", "020 8845 9470",
     "West End Road, Northolt, Middlesex UB5 6RE", None),
    ("Darji Mitra Mandal", "GB", "London", "info@darjimandal.org.uk", None,
     "The Darji Pavilion, 26 Oakthorpe Road, London N13 5JL", None),
    ("Federation of Patidar Associations", "GB", "Wembley", "info@patidars.org", "020 8795 1648",
     "Patidar House, 22 London Road, Wembley, Middlesex HA9 7EX", "Also 020 8902 1974."),
    ("KPS Gujarati School", "GB", "Harrow", "info@kpsgujaratischool.org", "020 8930 5046",
     "Kenmore Park First and Middle School, Moorhouse Road, Kenton, Harrow HA3 9JA", None),
    ("The Jain Centre (London)", "GB", "London", "info@jainnetwork.com", "020 8200 0828",
     "64 to 68 Colindale Avenue, London NW9 5DR", None),
    ("Gujarati Literary Academy", "GB", "Wembley", "editor@gla.org.uk", None,
     "2 Beechcroft Gardens, Wembley, Middlesex", None),
    # USA (several were filed under other countries; the addresses are in the US)
    ("Gujarati Cultural Association of Bay Area", "US", "Fremont", "info@gcabayarea.org", None,
     "46560 Fremont Blvd #109, Fremont, CA 94538", "Listed under Australia; the address is in California."),
    ("Gujarati Samaj of Atlanta", "US", "Atlanta", "info@gsatlanta.org", "770 496 0081",
     "Sardar Patel Bhavan, 5331 Royal Woods Parkway, Tucker, GA 30084", "Listed three times."),
    ("Gujarati Cultural Association of Utah", "US", "South Jordan", "gcautah@gmail.com", None,
     "PO Box 95468, South Jordan, UT 84095", "Listed under Jordan; the address is South Jordan, Utah."),
    ("Gujarati Samaj of Columbia, Missouri", "US", "Columbia", "dirgeshpatel@netzero.com", "573 239 2121",
     "3101 S Providence Rd, Columbia, MO 65203", "Listed under Malaysia; the address is in Missouri."),
    ("Gujarati Samaj of Portland", "US", "Portland", None, "503 287 5788", "PO Box 6033, Portland, OR 97228",
     "Listed twice."),
    ("Charotar Leuva Patidar Seva Samaj", "US", "Edison", None, "866 636 2925",
     "c/o Meena Patel, 6 Cedarwood Drive, Edison, NJ 08820", "Listed under UK; the address is in New Jersey."),
    ("DFW Gujarati Samaj", "US", "Dallas", "dfwgujaratisamaj@gmail.com", "949 795 6333",
     "777 S Central Expwy, Suite 7F, Richardson, TX 75080",
     "Listed under UK; the address is in Texas. President Atman Raval; Vice President Kanji Badhiwala 214 793 8083."),
    ("Gujarati Association of New England", "US", "Westford", None, "978 392 8683",
     "17 Hyacinth Drive, Westford, MA 01886", "Listed under UK; the address is in Massachusetts."),
    ("Patidar Samaj of New England", "US", "Salem", None, "978 741 3375", "34 Ord Street, Salem, MA", None),
    ("Gujarati Samaj of Tampa Bay", "US", "Tampa", None, "727 858 4123",
     "1211 N Westshore Blvd, Suite 104, Tampa, FL 33607", None),
    ("Kadva Patidar Samaj", "US", "Hanover Park", None, None, "7639 Manchester Manor, Hanover Park, IL 60103", None),
    ("Gujarati Samaj Chicago", "US", "Chicago", "gujchicago@gmail.com", "708 955 4966",
     "PO Box 267, Westmont, IL 60559", "Listed twice."),
    ("Gujarati Samaj of Greater Kansas City", "US", "Kansas City", "kcgujaratisamaj@gmail.com", "913 777 4715",
     "PO Box 7711, Overland Park, KS 66207", None),
    ("Gujarati Samaj of Louisiana", "US", "Alexandria", None, None, "5915 Bayou Robert Drive, Alexandria, LA 71301", None),
    ("Gujarati Samaj of Baltimore", "US", "Baltimore", None, None, "PO Box 687, Owings Mills, MD 21117",
     "Phone listed as 521 038 3400, which is not a valid US number."),
    ("Sabarkantha Leuva Patidar Samaj", "US", "Alma", None, None, "PO Box 651, Alma, MI 48801", None),
    ("Patidar Cultural Association of USA", "US", "Marlboro", None, "732 761 9829",
     "32 Stevenson Drive, Marlboro, NJ 07746", None),
    ("Gujarati Samaj of New York", "US", "New York", "gsnyweb@hotmail.com", "718 357 8651",
     "173-15 Horace Harding Expressway, Flushing, NY 11365", "Listed twice."),
    ("Charotar Patidar Samaj SE", "US", "Charlotte", None, "704 364 5255",
     "5113 Piper Station Road, Suite 300, Charlotte, NC 28277", None),
    ("Vishwa Gujarati Samaj USA", "US", "Schaumburg", "info@vishwagujaratisamajusa.org", "847 361 5545",
     "824 Spring Valley Court, Schaumburg, IL 60193", None),
    ("Gujarati Association of Connecticut", "US", "New Haven", None, "203 676 5075",
     "The Belvedere, 70 Pond Lily Ave, New Haven, CT 06515",
     "President Harry Patel; Vice President Shaku Patel 203 668 5797. Also listed with Prakash H Shah 203 996 5311."),
    ("Leuva Patidar Samaj of USA", "US", "Brentwood", "info@lpsofusa.com", "+1 866 201 2353",
     "9005 Overlook Blvd, Brentwood, TN 37027", None),
    ("Gujarati Samaj of Metropolitan Washington", "US", "Washington", None, "703 449 0772",
     "12665 Braddock Farms Court, Clifton, VA 20124", None),
    ("Brahmin Samaj of Georgia", "US", "Atlanta", "jyotishi_j@elmg.com", "770 662 8628", "PO Box 80162, Atlanta, GA",
     "Contacts: Chittaranjanbhai Jyotishi, Indubhai Raval 770 414 8565, Chetanbhai Vyas 770 300 0688."),
    ("California Darji Samaj", "US", "Elk Grove", None, None, "3824 Babson Drive, Elk Grove, CA 95758", None),
    ("Gujarati Samaj Inc (Richardson)", "US", "Richardson", None, "972 307 7890", "104 Inge Drive, Richardson, Texas",
     "Also 972 599 7749."),
    ("Gujarati Samaj of Austin", "US", "Austin", "contact@gujaustin.org", None, "PO Box 204231, Austin, TX 78720",
     "Listed three times."),
    ("Federation of Gujarati Associations of North America (FOGANA)", "US", "Wenham", None, "978 468 3900",
     "Wenham, Massachusetts 01984", None),
    ("California Gujarati Cultural Association", "US", "Rowland Heights", None, "909 594 0304",
     "2170 Carly Court, Rowland Heights, CA", "Also 909 594 7757."),
    ("Seattle Gujarati Cultural Society", "US", "Seattle", "akt@skilling.com", "206 364 8183",
     "PO Box 75601, Seattle, WA", None),
    ("Association of Indians in America", "US", "Oyster Bay", "surinder@sunpublish.com", "516 624 2460",
     "26 Pleasant Lane, Oyster Bay, NY 11771", None),
    ("Gujarati Samaj of Houston", "US", "Houston", "amee@gshouston.org", "832 279 2006",
     "PO Box 720733, Houston, TX 77272", None),
    ("Gujarati Samaj of Greater Pittsburgh", "US", "Pittsburgh", None, None, "2617 Bingham Dr, Pittsburgh, PA 15241", None),
    ("Karamsad Samaj of USA", "US", "Iselin", "info@karamsadsamaj.com", None, "227 Lincoln Highway, Iselin, NJ 08830", None),
    ("Bhadran Samaj of North America", "US", "New York", "mrpatel886@gmail.com", "609 468 1212",
     "41-31 51st St, Apt 5C, Woodside, NY 11377",
     "Contact: Mahendra S Patel. Also 908 421 1600 (Pankesh), 609 936 8773 (Praful)."),
    ("Charlotte Gujarati Samaj", "US", "Charlotte", "nimishbhatt@bellsouth.net", "704 491 1186",
     "7701 Wallace Lane, Charlotte, NC 28212", "Contact: Nimish Bhatt."),
    ("Sorathia Darji Samaj of America", "US", "Sugar Land", "rpjethva@hotmail.com", "281 491 6105",
     "c/o Ramesh P Jethva, 815 Skimmer Ct, Sugar Land, TX 77478", "Also Rupesh Makwana 281 242 7217."),
    ("Brahmin Samaj of USA", "US", "Edison", "bsouorg@yahoo.com", "201 659 3614", "2101 Merrywood Drive, Edison, NJ 08817", None),
    ("Brahmin Samaj of Florida", "US", "Sanford", "jignesh_vyas@mybsfl.com", "407 302 6011",
     "6148 Hedgesparrows Lane, Sanford, FL 32771", None),
    ("Gujarati Samaj of Sacramento", "US", "Sacramento", "info@gujsac.org", "+1 224 522 2007",
     "4279 Sardonyx Way, Rancho Cordova, CA 95742", None),
]

# Bodies already in the engine: fill empty fields and add the directory details to the notes.
EXISTING = [
    ("Shri Gujarati Samaj Bahrain", "BH", "info@shreegujaratisamajbahrain.org", None,
     "Villa 340, Road 3809, Block 338, Adliya; PO Box 1391", "Contact: Shailesh R Shah, listed as 9733924285."),
    ("Gujarati Samaj Qatar", "QA", None, None, "Qatar Petroleum (Offshore), PO Box 47, Doha",
     "Listed president: I C Patel, 5544 7107."),
    ("Gujarati Samaj Abu Dhabi", "AE", None, None, None,
     "Listed president: Tushar Patni +971 50 641 4126; Vice President Virendra Dave 050 615 0786."),
    ("Muscat Gujarati Samaj (Indian Social Club Oman)", "OM", None, None,
     "Indian Social Club, PO Box 19, PC 100, Muscat",
     "Listed president: Chandrakant V Chothani, cvchothani@gmail.com, +968 9934 6083."),
]


def _note(address, extra):
    parts = [CAVEAT]
    if address:
        parts.append(f"Address: {address}.")
    if extra:
        parts.append(extra)
    return " ".join(parts)


def apply_directory(conn):
    row = conn.execute("SELECT value FROM meta WHERE key = 'directory_version'").fetchone()
    if row and row[0] == DIRECTORY_VERSION:
        return 0
    approaches = {}

    def approach_for(country):
        if country not in approaches:
            conn.execute(
                """INSERT OR IGNORE INTO approaches (country, name, our_brief, template_kind, status, created_at)
                   VALUES (?, 'Community webinars', ?, 'community', 'active', ?)""",
                (country, COMMUNITY_BRIEF, now()),
            )
            approaches[country] = conn.execute(
                "SELECT id FROM approaches WHERE country = ? AND name = 'Community webinars'", (country,)
            ).fetchone()["id"]
        return approaches[country]

    added = 0
    for name, country, city, email, phone, address, extra in D:
        cur = conn.execute(
            """INSERT OR IGNORE INTO organisations
               (name, kind, country, city, contact_email, contact_phone, source_url, source_note, created_at)
               VALUES (?, 'community', ?, ?, ?, ?, ?, ?, ?)""",
            (name, country, city, email, phone, SOURCE, _note(address, extra), now()),
        )
        added += cur.rowcount
        org_id = conn.execute(
            "SELECT id FROM organisations WHERE name = ? AND country = ?", (name, country)
        ).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO tasks (approach_id, org_id, created_at) VALUES (?, ?, ?)",
            (approach_for(country), org_id, now()),
        )
    for name, country, email, phone, address, extra in EXISTING:
        org = conn.execute("SELECT * FROM organisations WHERE name = ? AND country = ?", (name, country)).fetchone()
        if org is None:
            continue
        if email and not org["contact_email"]:
            conn.execute("UPDATE organisations SET contact_email = ? WHERE id = ?", (email, org["id"]))
        if phone and not org["contact_phone"]:
            conn.execute("UPDATE organisations SET contact_phone = ? WHERE id = ?", (phone, org["id"]))
        note = "Directory: " + _note(address, extra)
        if CAVEAT not in (org["source_note"] or ""):
            joined = ((org["source_note"] or "").rstrip() + "\n\n" + note).strip()
            conn.execute("UPDATE organisations SET source_note = ? WHERE id = ?", (joined, org["id"]))
    conn.execute("DELETE FROM meta WHERE key = 'directory_version'")
    conn.execute("INSERT INTO meta (key, value) VALUES ('directory_version', ?)", (DIRECTORY_VERSION,))
    conn.commit()
    return added
