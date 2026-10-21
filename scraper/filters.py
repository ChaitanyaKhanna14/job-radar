"""Decide whether a posting is an India-based, fresher-level role worth showing."""
import html
import re
from html.parser import HTMLParser

INDIA_RE = re.compile(
    r"\b(india|bengaluru|bangalore|mumbai|new delhi|delhi|ncr|gurgaon|gurugram|noida|hyderabad|pune|"
    r"chennai|kolkata|ahmedabad|jaipur|kochi|coimbatore|indore|chandigarh|thiruvananthapuram|trivandrum|"
    r"mohali|vadodara|nagpur|bhubaneswar|mysore|mysuru|karnataka|maharashtra|telangana|tamil nadu|haryana)\b",
    re.I,
)

SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|snr|lead|leader|principal|staff|manager|director|head|vp|vice president|architect|"
    r"chief|distinguished|fellow|expert|supervisor|ii|iii|iv|l[4-9]|ic[3-9]|mts\s*[2-9]|smts|lmts|pmts)\b",
    re.I,
)
LEVEL_NUM_RE = re.compile(r"\b(engineer|engr|developer|analyst|sde|scientist|associate|consultant|qa|test)\s*[-,]?\s*(2|3|4|5)\b", re.I)
MANAGER_OK_RE = re.compile(r"associate product manager|product manager,? intern|\bapm\b|management trainee|manager intern", re.I)

FRESHER_TITLE_RE = re.compile(
    r"\b(intern|internship|interns|trainee|graduate|grad|fresher|freshers|entry[- ]level|early career|campus|"
    r"university|apprentice|junior|jr\.?|associate|new college|sde\s*-?\s*(1|i)|engineer\s*-?\s*(1|i)|"
    r"developer\s*-?\s*(1|i)|analyst\s*-?\s*(1|i)|20(26|27))\b",
    re.I,
)
FRESHER_JD_RE = re.compile(
    r"\b(freshers?|new grads?|recent graduates?|graduating in|class of 20\d\d|20(26|27) (batch|graduates?|pass ?outs?)|"
    r"0\s*(-|–|to)\s*[12]\s*(\+\s*)?years?|entry[- ]level|campus hir\w*|no prior experience|final[- ]year students?)\b",
    re.I,
)
INTERN_RE = re.compile(r"\b(intern|internship|interns|trainee|apprentice|co-?op)\b", re.I)

YEARS_RE = re.compile(
    r"(?:at least|minimum(?: of)?|min\.?)?\s*(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs?)",
    re.I,
)

CATEGORIES = [
    ("Product", re.compile(r"\b(product manager|apm|product analyst|product owner|program manager|product management|product)\b", re.I)),
    ("Analyst", re.compile(r"\b(analyst|analytics|data scien\w+|business intelligence|bi developer|insights|quant\w*|research)\b", re.I)),
    ("Business", re.compile(r"\b(business development|bd|bdr|sdr|sales|account executive|account manager|partnerships?|growth|"
                            r"consultant|consulting|strateg\w*|operations|representative|account development|deployment|customer success|solutions? (engineer|consultant)|presales|go[- ]to[- ]market|marketing)\b", re.I)),
    ("Engineering", re.compile(r"\b(software|sde|swe|developer|engineer|engineering|front[- ]?end|back[- ]?end|full[- ]?stack|web|mobile|"
                               r"android|ios|devops|sre|cloud|machine learning|ml|ai|data|qa|test|security|platform|programmer|technology)\b", re.I)),
]

EXCLUDE_RE = re.compile(
    r"\b(mechanical|electrical|civil|chemical|analog|rf|vlsi|asic|layout|silicon|hardware|pcb|manufacturing|"
    r"process engineer|field service|technician|nurse|legal|counsel|paralegal|accountant|accounting|tax|audit|payroll|"
    r"recruit\w*|talent acquisition|human resources|hr|facilities|driver|warehouse|delivery partner|chef|"
    r"design verification|physical design|mask|lithography|firmware|embedded|signal integrity|"
    r"teacher|tutor|faculty|copywriter|graphic designer|video editor|collections?|telecaller|call centre|bpo|"
    r"executive assistant|administrative|receptionist|kyc|aml|fincrime|fraud|investigation|escalation|maintenance|"
    r"reliability|support|content|language|linguist|catalog\w*|seller|customer service|transaction|back office|"
    r"data entry|annotat\w*|transcription|banking operations|operations specialist|process (associate|executive|excellence|specialist)|"
    r"reconciliation|settlement|derivatives|billing|procurement|warehouse|fleet|captain|relationship manager|"
    r"phd|post-?doc|quality associate|security guard|loss prevention|slp|avp|mid-?level|administrator|coordinator|"
    r"verification|cabling|data center (tech|material)|material associate|operations (associate|executive|coordinator)|"
    r"advocacy|campaign operations|supply chain associate|icqa|reference data|cap planning|wfm|expense|reimbursement|"
    r"customer operations|data validation|financial representative|infrastructure tech)\b",
    re.I,
)

LPA_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:(?:-|–|to)\s*(\d{1,3}(?:\.\d+)?)\s*)?(lpa|lakhs?\s*per\s*annum|lakhs?|lacs?)\b", re.I)


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "tr", "section"}

    def __init__(self):
        super().__init__()
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.out.append("\n• ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        self.out.append(data)


def html_to_text(raw):
    if not raw:
        return ""
    raw = html.unescape(raw)
    if "<" in raw:
        p = _Text()
        p.feed(raw)
        raw = "".join(p.out)
    raw = raw.replace("\xa0", " ")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    return raw.strip()


def is_india(location):
    return bool(location and INDIA_RE.search(location))


def min_years(text):
    """Smallest 'N years' requirement mentioned near the word experience, or None."""
    found = []
    for m in YEARS_RE.finditer(text or ""):
        window = text[max(0, m.start() - 80): m.end() + 80].lower()
        if "experience" in window or "exp" in window:
            n = int(m.group(1))
            if n <= 15:
                found.append(n)
    return min(found) if found else None


def category(title):
    for name, rx in CATEGORIES:
        if rx.search(title):
            return name
    return None


def salary_lpa(text):
    """Return (display string, max value in lakhs) for the first LPA-style figure, else (None, None)."""
    m = LPA_RE.search(text or "")
    if not m:
        return None, None
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) else lo
    if hi > 200:  # not a salary
        return None, None
    return m.group(0).strip(), hi


TITLE_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs?)", re.I)


def title_passes(title):
    """Cheap first pass on the title alone (used before fetching full descriptions)."""
    if not title or EXCLUDE_RE.search(title):
        return False
    m = TITLE_YEARS_RE.search(title)
    if m and int(m.group(1)) >= 2:
        return False
    if (SENIOR_RE.search(title) or LEVEL_NUM_RE.search(title)) and not MANAGER_OK_RE.search(title):
        return False
    return category(title) is not None


def classify(title, description, employment_type="", lenient=False):
    """Full check. Returns dict(type, category, salary) when the role fits, else None.

    lenient=True is for sources that only give a snippet of the description (the search
    query already targeted fresher roles), so a missing experience line is not held against it."""
    if not title_passes(title):
        return None
    desc = description or ""
    intern = bool(INTERN_RE.search(title) or INTERN_RE.search(employment_type or ""))
    years = min_years(desc)
    title_signal = bool(FRESHER_TITLE_RE.search(title) or MANAGER_OK_RE.search(title))
    jd_signal = bool(FRESHER_JD_RE.search(desc))

    if intern:
        ok = True
    elif years is not None and years >= 2:
        ok = False
    elif title_signal or jd_signal:
        ok = years is None or years <= 1
    else:
        ok = years is not None and years <= 1 or (lenient and years is None)

    if not ok:
        return None

    sal_text, sal_hi = salary_lpa(desc)
    if sal_hi is not None and not intern and sal_hi < 8:
        return None
    return {"type": "Internship" if intern else "Full-time", "category": category(title), "salary": sal_text}
