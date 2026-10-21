"""Companies to scan, grouped by the job-board system (ATS) they publish on.

Every company here is one that is known to pay freshers at or above ~8 LPA
(full-time CTC) in India. Add or remove entries freely; a slug that stops
working is skipped and reported in the run log.
"""

GREENHOUSE = {
    # slug: display name
    "okta": "Okta", "databricks": "Databricks", "mongodb": "MongoDB", "zscaler": "Zscaler",
    "highradius": "HighRadius", "stripe": "Stripe", "inmobi": "InMobi", "rubrik": "Rubrik",
    "sigmoid": "Sigmoid", "gitlab": "GitLab", "squarepointcapital": "Squarepoint Capital",
    "glance": "Glance", "hackerrank": "HackerRank", "imc": "IMC Trading", "toast": "Toast",
    "elastic": "Elastic", "twilio": "Twilio", "agoda": "Agoda", "datadog": "Datadog",
    "druva": "Druva", "groww": "Groww", "towerresearchcapital": "Tower Research Capital",
    "coinbase": "Coinbase", "newrelic": "New Relic", "airbnb": "Airbnb", "sumologic": "Sumo Logic",
    "anthropic": "Anthropic", "mixpanel": "Mixpanel", "observeai": "Observe.AI", "samsara": "Samsara",
    "adyen": "Adyen", "figma": "Figma", "vercel": "Vercel", "scaleai": "Scale AI",
    "wehrtyou": "Hudson River Trading", "cloudflare": "Cloudflare", "janestreet": "Jane Street",
    "slice": "slice", "clear": "Clear (ClearTax)", "purestorage": "Pure Storage", "celonis": "Celonis",
    "truecaller": "Truecaller", "deliveroo": "Deliveroo", "groupon": "Groupon", "workato": "Workato",
    "thoughtworks": "Thoughtworks",
}

LEVER = {
    "paytm": "Paytm", "meesho": "Meesho", "hevodata": "Hevo Data", "zeta": "Zeta",
    "mindtickle": "Mindtickle", "fampay": "FamPay", "ion": "ION Group", "cred": "CRED",
    "nium": "Nium", "pocketfm": "Pocket FM",
}

ASHBY = {
    "tekion": "Tekion", "sarvam": "Sarvam AI", "openai": "OpenAI", "harvey": "Harvey",
    "snowflake": "Snowflake", "cursor": "Cursor", "atlan": "Atlan", "notion": "Notion",
    "amplitude": "Amplitude", "navi": "Navi", "bureau": "Bureau", "spotdraft": "SpotDraft", "uipath": "UiPath",
}

SMARTRECRUITERS = {
    "swiggy": "Swiggy", "freshworks": "Freshworks", "wise": "Wise", "ixigo": "ixigo",
    "grab": "Grab", "servicenow": "ServiceNow", "canva": "Canva", "unacademy": "Unacademy",
    "bytedance": "ByteDance", "cars24": "CARS24", "mindtickle": "Mindtickle",
}

# (tenant, wd-number, site, display name)
WORKDAY = [
    ("salesforce", 12, "External_Career_Site", "Salesforce"),
    ("adobe", 5, "external_experienced", "Adobe"),
    ("nvidia", 5, "NVIDIAExternalCareerSite", "NVIDIA"),
    ("intel", 1, "External", "Intel"),
    ("mastercard", 1, "CorporateCareers", "Mastercard"),
    ("paypal", 1, "jobs", "PayPal"),
    ("target", 5, "targetcareers", "Target"),
    ("ms", 5, "External", "Morgan Stanley"),
    ("hp", 5, "ExternalCareerSite", "HP"),
    ("workday", 5, "Workday", "Workday"),
    ("autodesk", 1, "Ext", "Autodesk"),
    ("cisco", 5, "Cisco_Careers", "Cisco"),
    ("citi", 5, "2", "Citi"),
    ("db", 3, "DBWebSite", "Deutsche Bank"),
    ("barclays", 3, "External_Career_Site_Barclays", "Barclays"),
    ("kla", 1, "Search", "KLA"),
    ("analogdevices", 1, "External", "Analog Devices"),
    ("cadence", 1, "External_Careers", "Cadence"),
    ("thomsonreuters", 5, "External_Career_Site", "Thomson Reuters"),
    ("blackrock", 1, "BlackRock_Professional", "BlackRock"),
    ("nasdaq", 1, "Global_External_Site", "Nasdaq"),
    ("lseg", 3, "Careers", "LSEG"),
]
