"""Keyword-based categorizer for UAE bank statement descriptions."""

import re

# ---------------------------------------------------------------------------
# Keyword → (merchant_display_name, category)
# Order matters: first match wins.  More specific patterns come before
# broader ones (e.g. "SPINNEYS-K" grocery before "SPINNEYS" food).
# ---------------------------------------------------------------------------

_KEYWORD_RULES: list[tuple[str, str, str]] = [
    # ── Cheque Deposit (must be before Internal Transfers — cheque descs contain account holder name) ──
    ("INHOUSE CHEQUE DEPOSIT", "Cheque Deposit", "Cheque Deposit"),
    ("PDC CHEQUE DEPOSIT", "Cheque Deposit", "Cheque Deposit"),
    ("CHEQUE DEPOSIT", "Cheque Deposit", "Cheque Deposit"),
    ("CHDP", "Cheque Deposit", "Cheque Deposit"),

    # ── Internal Transfers (must be before generic Transfer) ──────────
    ("RASHED ALI AHMED HAMAD ALDHAHERI", "Internal Transfer", "Internal Transfers"),
    ("RASHED ALI ALDHAHERI", "Internal Transfer", "Internal Transfers"),

    # ── Credit Card Payment ───────────────────────────────────────────
    ("CREDIT CARD PAYMNT", "Credit Card Payment", "Credit Card Payment"),

    # ── Cash Withdrawal ──────────────────────────────────────────────
    ("ATM WDL", "ATM Withdrawal", "Cash Withdrawal"),

    # ── Cheque Payment / Withdrawal ───────────────────────────────────
    ("CHEQUE WITHDRAWAL", "Cheque Withdrawal", "Cheque Deposit"),
    ("I/W CLEARING CHEQUE", "Clearing Cheque", "Cheque Deposit"),

    # ── Salary & Allowances ──────────────────────────────────────────
    ("/REF/ALLOWANCE", "Allowance", "Allowance"),

    # ── Loan ─────────────────────────────────────────────────────────
    ("INSTALLMENT RECOVERY", "Loan Installment", "Loan"),

    # ── Interest & Cash Back Earnings ─────────────────────────────────
    ("PROFIT PAID", "Profit / Interest", "Interest & Cash Back Earnings"),
    ("CASHBACK", "Cashback", "Interest & Cash Back Earnings"),
    ("CASH BACK", "Cashback", "Interest & Cash Back Earnings"),

    # ── Credit Card Payment (CC statement side — inflow) ─────────────
    ("PAYMENT RECEIVED, THANK YOU", "Credit Card Payment", "Credit Card Payment"),

    # ── Refund ───────────────────────────────────────────────────────
    ("REFUND", "Refund", "Refund"),

    # ── Bank Charges ─────────────────────────────────────────────────
    ("MB BILL DR", "Bank Charges", "Bank Charges"),
    ("TRANSFER FEE", "Transfer Fee", "Bank Charges"),

    # ── Transfer recipients (specific → category, before generic transfer) ──
    ("INAYA DOMESTIC WORKERS", "Inaya Domestic Workers", "Maid Expenses"),
    ("PRESLYN DALAFU RAMOS", "Preslyn Dalafu Ramos", "Maid Expenses"),
    ("SHIHAB KALLINGAL", "Shihab Kallingal", "Maid Expenses"),
    ("MKR PLACEMENT", "MKR Placement Agencies", "Maid Expenses"),
    ("SHABIH UL HASSAN", "Shabih Ul Hassan", "Maid Expenses"),
    ("ZIA UL HASSAN", "Zia Ul Hassan", "Maid Expenses"),
    ("MUNA ALDHAHERI", "Muna AlDhaheri", "Allowance"),
    ("HESSA ALI", "Hessa Ali AlDhaheri", "Charity"),
    ("JAMALUDEEN", "Jamaludeen Arayalan", "Charity"),
    ("ABDULLA AHMED SHABEEB", "Abdulla Ahmed Shabeeb", "Family Transfer"),
    ("MAITHA ALI", "Maitha Ali AlDhaheri", "Family Transfer"),
    ("SAEED AHMED SHABEEB", "Saeed Ahmed Shabeeb", "Family Transfer"),
    ("MOHAMMED NAJMAL", "Mohammed Najmal", "Bills"),
    ("THE STABLES STORAGE", "The Stables Storage", "Car Expenses"),

    # ── Transfer (generic — unidentified by default) ───────────────
    ("MBTRF", "Bank Transfer", "Unidentified"),
    ("TRF OUT TO", "Transfer Out", "Unidentified"),
    ("TRF B/O", "Transfer In", "Unidentified"),

    # ── Real Estate ──────────────────────────────────────────────────
    ("PATTATHU", "Rent – Pattathu", "Real Estate"),
    ("CASH DEPOSIT-RENT", "Rent Deposit", "Real Estate"),

    # ── Groceries (before generic food keywords) ─────────────────────
    ("SPINNEYS-K", "Spinneys", "Groceries"),
    ("SPINNEYS-M", "Spinneys", "Groceries"),
    ("LULU HYPERMARKET", "Lulu Hypermarket", "Groceries"),
    ("WAITROSE A", "Waitrose", "Groceries"),
    ("AL MUSHRIF CO OPERAT", "Al Mushrif Co-Op", "Groceries"),
    ("AMAZON GROCERY", "Amazon Grocery", "Groceries"),
    ("ADCOOPS", "AD Co-Ops", "Groceries"),

    # ── Food & Dining ────────────────────────────────────────────────
    ("ALL DAY MA", "All Day Market", "Food & Dining"),
    ("AL EQABIA", "Al Eqabia", "Food & Dining"),
    ("ZOI CA", "Zoi Cafe", "Food & Dining"),
    ("NAKHAT TAH", "Nakhat Tahi", "Food & Dining"),
    ("SAVE OUR S", "Save Our Souls", "Food & Dining"),
    ("AL HABARA", "Al Habara Cafeteria", "Food & Dining"),
    ("SNACKAT", "Snackat Cafe", "Food & Dining"),
    ("DIN TAI FUNG", "Din Tai Fung", "Food & Dining"),
    ("TALABAT", "Talabat", "Food & Dining"),
    ("DELIVEROO", "Deliveroo", "Food & Dining"),
    ("STARBUCKS", "Starbucks", "Food & Dining"),
    ("MCDONALDS", "McDonald's", "Food & Dining"),
    ("FIVE GUYS", "Five Guys", "Food & Dining"),
    ("ZOI CAFE", "Zoi Cafe", "Food & Dining"),
    ("THE GROVE", "The Grove", "Food & Dining"),
    ("BEANZ GENE", "Beanz Gene", "Food & Dining"),
    ("TURIN EXPR", "Turin Express", "Food & Dining"),
    ("BLU PIZZER", "Blu Pizzeria", "Food & Dining"),
    ("OLA BRASIL", "Ola Brasil", "Food & Dining"),
    ("SIMPLE SNA", "Simple Snack", "Food & Dining"),
    ("NASH HOT", "Nash Hot", "Food & Dining"),
    ("TIFFAN CAF", "Tiffany Cafe", "Food & Dining"),
    ("ERGON DELI", "Ergon Deli", "Food & Dining"),
    ("OTORO REST", "Otoro Restaurant", "Food & Dining"),
    ("BERENJAK", "Berenjak", "Food & Dining"),
    ("SADDLE CAF", "Saddle Cafe", "Food & Dining"),
    ("CAPTAIN PROTEIN", "Captain Protein", "Food & Dining"),
    ("CARREFOUR", "Carrefour", "Food & Dining"),
    ("AL SAFA CO", "Al Safa", "Food & Dining"),
    ("COULD BE C", "Could Be Croissant", "Food & Dining"),
    ("AL FANAR", "Al Fanar", "Food & Dining"),
    ("EMIRATES R ABU DHABI", "Emirates Restaurant", "Food & Dining"),
    ("78 LOUNGE", "78 Lounge", "Food & Dining"),
    ("TEZUKURI", "Tezukuri", "Food & Dining"),
    ("THE URBN P", "The Urban P", "Food & Dining"),
    ("DRVN COFFE", "DRVN Coffee", "Food & Dining"),
    ("ROWLEYS ST", "Rowley's Steakhouse", "Food & Dining"),
    ("ONE ZAABEE", "One Zaabeel", "Food & Dining"),
    ("SPINNEYS", "Spinneys", "Food & Dining"),
    ("WAITROSE", "Waitrose", "Food & Dining"),

    # ── Shopping ──────────────────────────────────────────────────────
    ("MAMO*BLOOM", "Bloom", "Shopping"),
    ("SP SHOP SR", "SP Shop SRAM", "Shopping"),
    ("SP IM8 HEA", "SP IM8 Health", "Shopping"),
    ("SP STAY FI", "SP Stay Fit", "Shopping"),
    ("SP BRICK L", "SP Brick L", "Shopping"),
    ("SP BLOOM I", "SP Bloom", "Shopping"),
    ("SP SENARAH", "Senarah", "Shopping"),
    ("MUMUSO", "Mumuso", "Shopping"),
    ("WEAR MART", "Wear Mart", "Shopping"),
    ("AL TELAL", "Al Telal Gents Fashion", "Shopping"),
    ("KOALAPICKS", "KoalaPicks", "Shopping"),
    ("UPCO JUNIOR", "Upco Junior", "Shopping"),
    ("FLYING TIGER", "Flying Tiger", "Shopping"),
    ("FLOWERLAB", "FlowerLab", "Shopping"),
    ("BRIGHT WAY", "Bright Way Trading", "Shopping"),
    ("BIN HAMOODAH", "Bin Hamoodah", "Shopping"),
    ("HARD ARISE", "Hard Arise Electric", "Shopping"),
    ("AMAZON.AE", "Amazon.ae", "Shopping"),
    ("AMAZON RETAIL", "Amazon", "Shopping"),
    ("AMAZON NOW", "Amazon Now", "Shopping"),
    ("AMAZONUFG", "Amazon", "Shopping"),
    ("TEMU", "Temu", "Shopping"),
    ("NOON.COM", "Noon", "Shopping"),
    ("NOON", "Noon", "Shopping"),
    ("VIRGIN MEGASTORE", "Virgin Megastore", "Shopping"),
    ("OUNASS", "Ounass", "Shopping"),
    ("BOOTS CC", "Boots", "Shopping"),
    ("R M K PERF", "RMK Perfumes", "Shopping"),
    ("CABOODLE", "Caboodle", "Shopping"),
    ("WWW ISCENT", "iScent", "Shopping"),
    ("CELL CITY", "Cell City", "Shopping"),
    ("A ONE ELEC", "A One Electronics", "Shopping"),
    ("MICROLESS", "Microless", "Shopping"),
    ("FIRSTCRY", "FirstCry", "Shopping"),
    ("WWW.SHEIN.COM", "Shein", "Shopping"),
    ("SHEIN", "Shein", "Shopping"),
    ("MAGRUDY", "Magrudy's", "Shopping"),
    ("STELLALUNA", "Stellaluna", "Shopping"),
    ("H AND M", "H&M", "Shopping"),
    ("AL MAYA", "Al Maya", "Shopping"),
    ("AWANI HOUSEWARES", "Awani Housewares", "Shopping"),
    ("BAB ALBUKHARI", "Bab AlBukhari", "Shopping"),
    ("BRANDS FOR LESS", "Brands For Less", "Shopping"),
    ("BUILDEX", "Buildex", "Shopping"),
    ("CREATIVE MINDS", "Creative Minds", "Shopping"),
    ("CRREFOUR", "Carrefour", "Shopping"),
    ("DAISO", "Daiso", "Shopping"),
    ("JAPAN VALUE", "Japan Value Store", "Shopping"),
    ("HRAYER", "Hrayer & Shifon", "Shopping"),
    ("ISHQ DESIGN", "Ishq Design Tailoring", "Shopping"),
    ("JACADI", "Jacadi", "Shopping"),
    ("KAMIN FOR LADIES", "Kamin Ladies Wear", "Shopping"),
    ("LITTLE SCISSORS", "Little Scissors", "Shopping"),
    ("MALAK HANDCRAFTED", "Malak Handcrafted", "Shopping"),
    ("MAVI SHOETIQUE", "Mavi Shoetique", "Shopping"),
    ("MINISO", "Miniso", "Shopping"),
    ("NEXTUAE", "Next UAE", "Shopping"),
    ("NOMOD", "Nomod", "Shopping"),
    ("PASHMINA", "Pashmina Shailaa", "Shopping"),
    ("PLP EVENTS", "PLP Events", "Shopping"),
    ("SUGAR AND SALT", "Sugar & Salt Station", "Shopping"),
    ("TAWASUL TRANSPORT", "Tawasul Transport", "Shopping"),
    ("BLUE BOX VENDING", "Blue Box Vending", "Shopping"),
    ("TICKETE", "Tickete", "Shopping"),
    ("TOYS R US", "Toys R Us", "Shopping"),
    ("INSTASHOP", "InstaShop", "Shopping"),
    ("ZIINA", "Ziina", "Shopping"),
    ("BREATH BY THE QLUB", "Breath by the Qlub", "Shopping"),
    ("CAPTURED PHOTOGRAPHY", "Captured Photography", "Shopping"),
    ("LENSMAN", "Lensman Photography", "Shopping"),
    ("LRIL", "LRIL", "Shopping"),
    ("GINGERWELLNESS", "GingerWellness", "Beauty & Personal Care"),
    ("GLAZA COLLECTION", "Glaza Collection", "Shopping"),
    ("P L P EVENTS", "PLP Events", "Shopping"),
    ("PUFF CAFE", "Puff Cafe", "Food & Dining"),
    ("RED CURRY", "Red Curry", "Food & Dining"),
    ("VIP FARMS", "VIP Farms", "Entertainment"),
    ("REDWOOD NURSERY", "Redwood Nursery", "Education"),

    # ── Transport ────────────────────────────────────────────────────
    ("CAREEM RID", "Careem", "Transport"),
    ("UBER *TRIP", "Uber", "Transport"),
    ("UBER", "Uber", "Transport"),
    ("ARABIA TAXI", "Arabia Taxi", "Transport"),
    ("CARS TAXI", "Cars Taxi", "Transport"),
    ("NOQODI GV", "Noqodi Parking", "Transport"),
    ("SRT CAR PA", "SRT Parking", "Transport"),

    # ── Software & Subscriptions ─────────────────────────────────────
    ("PADDLE.NET", "Paddle.net", "Software & Subscriptions"),
    ("GOOGLE*GOOGLE ONE", "Google One", "Software & Subscriptions"),
    ("WWW.PERPLEXITY", "Perplexity AI", "Software & Subscriptions"),
    ("CHATMIST", "ChatMist", "Software & Subscriptions"),
    ("CLAUDE.AI", "Claude AI", "Software & Subscriptions"),
    ("CLAUDE AI", "Claude AI", "Software & Subscriptions"),
    ("ANTHROPIC", "Anthropic", "Software & Subscriptions"),
    ("OPENAI", "OpenAI", "Software & Subscriptions"),
    ("GOOGLE ONE", "Google One", "Software & Subscriptions"),
    ("GOOGLE*WORKSPACE", "Google Workspace", "Software & Subscriptions"),
    ("ADOBE.COM", "Adobe", "Software & Subscriptions"),
    ("TODOIST", "Todoist", "Software & Subscriptions"),
    ("AIRTABLE", "Airtable", "Software & Subscriptions"),
    ("APIFY", "Apify", "Software & Subscriptions"),
    ("LOVABLE", "Lovable", "Software & Subscriptions"),
    ("EVERAI", "EverAI", "Software & Subscriptions"),
    ("DARLINK AI", "DarLink AI", "Software & Subscriptions"),
    ("DIGITALKWARTS", "DigitalKwarts", "Software & Subscriptions"),
    ("GOOGLE*YOUTUBEPREMIUM", "YouTube Premium", "Software & Subscriptions"),
    ("GOOGLE*REUTERS", "Reuters", "Software & Subscriptions"),
    ("GOOGLE*ALARMY", "Alarmy", "Software & Subscriptions"),
    ("GOOGLE*F1 TV", "F1 TV", "Software & Subscriptions"),
    ("GOOGLE*KITXOO", "Kitxoo", "Software & Subscriptions"),
    ("GOOGLE*MACRODROID", "MacroDroid", "Software & Subscriptions"),
    ("GOOGLE*TERMINALELEVEN", "Terminal Eleven", "Software & Subscriptions"),
    ("GOOGLE*PLAY BOOKS", "Google Play Books", "Software & Subscriptions"),
    ("GOOGLE*CHROME", "Google Chrome", "Software & Subscriptions"),
    ("IP2OPERATIONS", "IP2Operations", "Software & Subscriptions"),
    ("WWW.VIZER.AE", "Vizer", "Software & Subscriptions"),
    ("JWSBILL.COM", "JWS", "Software & Subscriptions"),
    ("SENDINBLUE", "Brevo (SendinBlue)", "Software & Subscriptions"),

    # ── Gaming ───────────────────────────────────────────────────────
    ("STEAMGAMES", "Steam", "Gaming"),
    ("WL *STEAM", "Steam", "Gaming"),
    ("STEAM", "Steam", "Gaming"),
    ("ITCH.IO", "itch.io", "Gaming"),
    ("XAI LLC", "Grok (xAI)", "Gaming"),

    # ── Electronics ──────────────────────────────────────────────────
    ("SAMSUNG", "Samsung", "Electronics"),
    ("DU SAMSUNG", "Samsung (du)", "Electronics"),
    ("DU APPLE P", "Apple (du)", "Electronics"),
    ("DU GOOGLE PAYMENT", "Google (du)", "Electronics"),
    ("E& DIGITAL", "e& Digital", "Electronics"),
    ("FAST TECHN", "Fast Technologies", "Electronics"),
    ("SHARAF DG", "Sharaf DG", "Electronics"),
    ("EMAX", "Emax", "Electronics"),

    # ── Fuel Expenses ──────────────────────────────────────────────
    ("ADNOC", "ADNOC", "Fuel Expenses"),

    # ── Car Expenses ──────────────────────────────────────────────
    ("PREMIER MOTORS LLC", "Premier Motors", "Car Expenses"),
    ("LIBERTY TYRE", "Liberty Tyre Center", "Car Expenses"),

    # ── Additional Healthcare ──────────────────────────────────────
    ("DOCTOR SHERIF", "Doctor Sherif Mattar", "Healthcare"),
    ("INTL CENTER FOR DENTAL", "Intl Center For Dental", "Healthcare"),
    ("N M C SPECIALTY", "NMC Specialty", "Healthcare"),
    ("MIMAR LADIES SPA", "Mimar Ladies Spa", "Healthcare"),

    # ── Bills ────────────────────────────────────────────────────────
    ("ADDC", "ADDC", "Bills"),
    ("ETISALAT", "Etisalat", "Bills"),

    # ── Traffic Fines & Fees ───────────────────────────────────────
    ("MINISTRY O", "Ministry", "Traffic Fines & Fees"),
    ("ABU DHABI POLICE", "Abu Dhabi Police", "Traffic Fines & Fees"),
    ("SAAED FOR", "Saaed", "Traffic Fines & Fees"),

    # ── Government ───────────────────────────────────────────────────
    ("TAMM", "TAMM", "Government"),
    ("DUBAIPAY", "DubaiPay", "Government"),

    # ── Healthcare ───────────────────────────────────────────────────
    ("THE ELIXIR POLY CLINIC", "The Elixir Polyclinic", "Healthcare"),
    ("AL MANARA", "Al Manara Pharmacy", "Healthcare"),
    ("NMC SPECIALTY", "NMC Specialty", "Healthcare"),
    ("AMBULATORY HEALTH", "Ambulatory Health", "Healthcare"),
    ("SERENITY H", "Serenity Health", "Healthcare"),
    ("NEW PHARMACY", "New Pharmacy", "Healthcare"),

    # ── Armed Forces (cafeteria / dining) ─────────────────────────────
    ("ARMED FORC", "Armed Forces", "Food & Dining"),

    # ── Hotels & Accommodation ───────────────────────────────────────
    ("DESERT ISLAND RESORT", "Desert Island Resort", "Hotels & Accommodation"),
    ("EMIRATES PALACE", "Emirates Palace", "Hotels & Accommodation"),
    ("SOFITEL PH", "Sofitel", "Hotels & Accommodation"),
    ("AL YAMM VI", "Al Yamm Villa", "Hotels & Accommodation"),
    ("ONE ZAABEEL HOTEL", "One Zaabeel Hotel", "Hotels & Accommodation"),
    ("INTERCONT", "InterContinental", "Hotels & Accommodation"),

    # ── Travel ───────────────────────────────────────────────────────
    ("EMIRATES000", "Emirates Airline", "Travel"),
    ("MYUS.COM", "MyUS", "Travel"),
    ("MOTOGP.COM", "MotoGP", "Travel"),
    ("DISNEY", "Disney", "Travel"),
    ("BLACKLANE", "Blacklane", "Travel"),

    # ── Charity ──────────────────────────────────────────────────────
    ("EMIRATES RED CRESCENT", "Emirates Red Crescent", "Charity"),

    # ── Insurance ────────────────────────────────────────────────────
    ("EMIRATES INSURANCE", "Emirates Insurance", "Insurance"),
    ("AIG LONDON", "AIG", "Insurance"),

    # ── Beauty & Personal Care ───────────────────────────────────────
    ("THE GROOMI", "The Grooming Co", "Beauty & Personal Care"),
    ("IVANA BEAUTY", "Ivana Beauty", "Beauty & Personal Care"),

    # ── Laundry & Dry Cleaning ───────────────────────────────────────
    ("JEEVES BELGRAVIA", "Jeeves", "Laundry & Dry Cleaning"),
    ("EVER CLEAN LAUNDRY", "Ever Clean Laundry", "Laundry & Dry Cleaning"),

    # ── Home & Furniture ─────────────────────────────────────────────
    ("IKEA", "IKEA", "Home & Furniture"),
    ("2 X L HOME", "2XL Home", "Home & Furniture"),
    ("2 XL HOME", "2XL Home", "Home & Furniture"),
    ("HOMES R US", "Homes R Us", "Home & Furniture"),

    # ── Entertainment ────────────────────────────────────────────────
    ("VOX CINEMA", "VOX Cinemas", "Entertainment"),
    ("VOX MARYAH", "VOX Cinemas", "Entertainment"),
    ("GLOBAL VIL", "Global Village", "Entertainment"),
    ("WWW INSTAS", "InstaSnap", "Entertainment"),
    ("EMIRATES NATURE", "Emirates Nature", "Entertainment"),

    # ── Education ───────────────────────────────────────────────────
    ("BATEEN WOR", "Bateen World Academy", "Education"),
    ("LEADRIGHT", "LeadRight", "Education"),
    ("UDEMY", "Udemy", "Education"),
    ("REDWOOD NUS", "Redwood Nursery", "Education"),

    # ── Traffic Penalties and Service Fees ──────────────────────────
    ("TRAFFIC PENALTIES", "Traffic Penalty", "Traffic Penalties and Service Fees"),

    # ── Miscellaneous catch-alls ────────────────────────────────────
    ("CAUBADE", "Caubade Phone", "Electronics"),
    ("EASYTIP", "EasyTip", "Food & Dining"),
    ("WOLFIS", "Wolfi's Bike Shop", "Shopping"),
    ("MRCR MOBILE", "MRCR Mobile Pay", "Shopping"),
    ("MARKS&SPENCER", "M&S", "Shopping"),
    ("AL FUTTAIM", "Al Futtaim", "Shopping"),
    ("ABU DHABI ISLAMIC BAN", "ADIB ATM", "Cash Withdrawal"),
    ("HSBC BANK MIDDLE", "HSBC ATM", "Cash Withdrawal"),
    ("LE TABAC", "Le Tabac Exclusivo", "Shopping"),
    ("FEDEX", "FedEx", "Shopping"),
    ("PMB*BREWIN", "Brewing Gadget", "Food & Dining"),
    ("LULUHYPERMARKET", "Lulu Hypermarket", "Groceries"),
    ("LULU HYPERMARKET", "Lulu Hypermarket", "Groceries"),
    ("GRAND EMIRATES MARKE", "Grand Emirates Market", "Groceries"),
    ("AL HABARA", "Al Habara", "Food & Dining"),
    ("FOOD TO GO", "Food To Go", "Food & Dining"),
    ("KISMATH", "Kismath Restaurant", "Food & Dining"),
    ("BEANZ GENERAL", "Beanz General Trading", "Food & Dining"),
    ("MAGIC BOARD", "Magic Board", "Shopping"),
    ("SAFA EXPRESS", "Safa Express", "Groceries"),
    ("LOVE SHORE GROCERY", "Love Shore Grocery", "Groceries"),
    ("LULU EXP FRESH", "Lulu Express", "Groceries"),
    ("BIGMART HYPERMARKET", "BigMart Hypermarket", "Groceries"),
    ("EARTH SUPERMARKET", "Earth Supermarket", "Groceries"),
    ("SPAR SAADIYAT", "Spar Saadiyat", "Groceries"),
    ("AIKO HYPER MARKET", "Aiko Hyper Market", "Groceries"),
    ("AL MUNAWARA GROCERY", "Al Munawara Grocery", "Groceries"),
    ("ABU DHABI  ABU DHABI", "Abu Dhabi Mall", "Entertainment"),
    ("ABU DHABI  ABUDHABI", "Abu Dhabi Mall", "Entertainment"),
    ("BRAG TWO F", "Brag Two F", "Food & Dining"),
    ("MADHAQ ALK", "Madhaq Alkheir", "Food & Dining"),
    ("POS*LULUWA", "Luluwa", "Food & Dining"),
    ("DUNES SPEC", "Dunes Special", "Shopping"),
    ("TEMU COM", "Temu", "Shopping"),
    ("AMAZON MKTPL", "Amazon Marketplace", "Shopping"),
    # ── New merchants from statement categorization ───────────────────
    ("COCO CAFE", "Coco Cafe & Playhouse", "Entertainment"),
    ("SANDS KIDS", "Sands Kids Entertainment", "Entertainment"),
    ("SHAKE SHACK", "Shake Shack", "Food & Dining"),
    ("CALICUT FLOWERS", "Calicut Flowers", "Food & Dining"),
    ("DILLY DARBAR", "Dilly Darbar", "Food & Dining"),
    ("FREAT RESTAURANT", "Freat Restaurant", "Food & Dining"),
    ("SAFARI PLAZA", "Safari Plaza Restaurant", "Food & Dining"),
    ("CALO", "Calo", "Food & Dining"),
    ("FAT*EMIRATES", "Emirates (FAT)", "Travel"),
    ("EMIRATE OF ABU DHABI FINANCE", "Abu Dhabi Finance Dept", "Allowance"),
    ("SAEED ALI ALDHAHERI", "Saeed Ali AlDhaheri", "Transfer"),
    ("CDM-CASH DEPOSIT", "Cash Deposit", "Cheque Deposit"),
    ("GOOGLE ALARMY", "Alarmy", "Software & Subscriptions"),
    ("GOOGLE WATER TRACKER", "Water Tracker", "Software & Subscriptions"),
    ("GOOGLE WORKSPACE", "Google Workspace", "Software & Subscriptions"),
    ("EMIRATES62", "Emirates Airline", "Travel"),
    ("STA AL SHA", "STA Al Sha", "Food & Dining"),
    ("J555 STARB", "Starbucks", "Food & Dining"),
    ("RUKN  AL A", "Rukn Al Ain", "Food & Dining"),
    ("AL FAIR AL", "Al Fair", "Groceries"),
    ("M H  ALSHA", "MH Al Sha", "Shopping"),
    ("ADIB HEAD", "ADIB", "Bank Charges"),
    ("YUBI HANDR", "Yubi Handraft", "Shopping"),
    ("YANN COUVR", "Yann Couvreur", "Food & Dining"),
    ("THE VALET", "The Valet", "Food & Dining"),
    ("TEN ELEVEN", "Ten Eleven", "Food & Dining"),
    ("FIRST CLAS", "First Class", "Food & Dining"),
    ("SHAY WAZAB", "Shay Wazab", "Food & Dining"),
    ("AMAZON RET", "Amazon", "Shopping"),
    ("AMAZON AE", "Amazon.ae", "Shopping"),
    ("SP SQUIDHA", "SquidHash", "Software & Subscriptions"),
    ("HOUSE OF TEA", "House of Tea", "Food & Dining"),
    ("WWW.AROMATIERRA", "Aromatierra", "Beauty & Personal Care"),
    ("MUNA ALDHAHERI", "Muna AlDhaheri", "Transfer"),
    ("MAITHA ALI", "Maitha Ali", "Transfer"),
    ("HESSA ALI", "Hessa Ali AlDhaheri", "Transfer"),
    ("JAMALUDEEN", "Jamaludeen", "Transfer"),
    ("ABDULLA AHMED", "Abdulla Ahmed", "Transfer"),
    ("SHIHAB KALLINGAL", "Shihab Kallingal", "Maid Expenses"),
    ("MOHAMMED NAJMAL", "Mohammed Najmal", "Transfer"),
    ("THE STABLES STORAGE", "The Stables Storage", "Other"),
    ("MKR PLACEMENT", "MKR Placement", "Transfer"),
    ("ZIA UL HASSAN", "Zia Ul Hassan", "Transfer"),
    ("SHABIH UL HASSAN", "Shabih Ul Hassan", "Transfer"),
    ("SAEED AHMED SHABEEB", "Saeed Ahmed Shabeeb", "Transfer"),

    # ── Maid Expenses ────────────────────────────────────────────────
    ("INAYA DOMESTIC WORKERS", "Inaya Domestic Workers", "Maid Expenses"),
    ("PRESLYN DALAFU RAMOS", "Maid – Preslyn", "Maid Expenses"),
]

# Pre-compile: uppercase keywords for case-insensitive matching
_COMPILED_RULES: list[tuple[str, str, str]] = [
    (kw.upper(), merchant, cat) for kw, merchant, cat in _KEYWORD_RULES
]

# ---------------------------------------------------------------------------
# Patterns for cleaning raw statement descriptions
# ---------------------------------------------------------------------------
_RE_PUR_PREFIX = re.compile(r"^PUR\s+\d{2}/\d{2}\s*", re.IGNORECASE)
_RE_CURRENCY_SUFFIX = re.compile(
    r"\s+(?:AMOUNT\s+)?(?:USD|EUR|GBP|SAR|INR|EGP|PKR)\s*[\d.,]+", re.IGNORECASE
)
_RE_CARD_SUFFIX = re.compile(r"\s+\d{4}\s*$")
_RE_CITY_SUFFIX = re.compile(
    r"\s+(?:ABU\s*DHABI|DUBAI|SHARJAH|AJMAN|AL\s*AIN|RAS\s*AL\s*KHAIM|FUJAIRAH|UAQ|UAE|AE)\s*$",
    re.IGNORECASE,
)
_RE_EXTRA_SPACES = re.compile(r"\s{2,}")


def _clean_description(raw: str) -> str:
    """Strip POS noise, currency info, card numbers, and city suffixes."""
    text = raw.strip()
    text = _RE_PUR_PREFIX.sub("", text)
    text = _RE_CURRENCY_SUFFIX.sub("", text)
    text = _RE_CARD_SUFFIX.sub("", text)
    text = _RE_CITY_SUFFIX.sub("", text)
    text = _RE_EXTRA_SPACES.sub(" ", text).strip()
    return text


def categorize(description: str, flow_type: str) -> tuple[str, str]:
    """Return (merchant_name, category) based on a bank statement description.

    Args:
        description: Raw description from the bank statement.
        flow_type: ``"Inflow"`` or ``"Outflow"`` — used for salary detection.

    Returns:
        A tuple of (cleaned merchant name, category string).
    """
    cleaned = _clean_description(description)
    raw_upper = description.upper()
    upper = cleaned.upper()

    # Exact salary match (inflow only)
    if upper.strip() == "SALARY" and flow_type == "Inflow":
        return ("Salary", "Salary")

    # Keyword scan — check both cleaned and raw description (first match wins)
    for keyword, merchant, category in _COMPILED_RULES:
        if keyword in upper or keyword in raw_upper:
            return (merchant, category)

    return (cleaned, "Other")
