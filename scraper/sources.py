"""One fetcher per job-board system. Each yields raw job dicts:
{company, title, location, url, description, posted, employment_type, salary_hint, source, ext_id}
"""
import concurrent.futures as cf
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from filters import html_to_text, is_india, title_passes

UA = {"User-Agent": "Mozilla/5.0 (job-radar; personal job search)", "Accept": "application/json"}


def http_json(url, body=None, retries=2, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA)
    if data:
        headers["Content-Type"] = "application/json"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:
            if attempt == retries:
                raise
            time.sleep(1.5 * (attempt + 1))


def _date(value):
    if not value:
        return None
    if isinstance(value, (int, float)):  # epoch millis
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def greenhouse(slug, name):
    d = http_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    for j in d.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        offices = " ".join(o.get("name", "") for o in j.get("offices") or [])
        if not (is_india(loc) or is_india(offices)) or not title_passes(j.get("title", "")):
            continue
        yield {
            "company": name, "title": j["title"], "location": loc or offices, "url": j.get("absolute_url"),
            "description": html_to_text(j.get("content")), "posted": _date(j.get("first_published") or j.get("updated_at")),
            "employment_type": "", "source": "Greenhouse", "ext_id": f"gh-{slug}-{j['id']}",
        }


def lever(slug, name):
    d = http_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    for j in d:
        cats = j.get("categories") or {}
        loc = cats.get("location") or ""
        all_locs = " ".join([loc] + (cats.get("allLocations") or []))
        if not is_india(all_locs) or not title_passes(j.get("text", "")):
            continue
        parts = [j.get("descriptionPlain") or ""]
        for lst in j.get("lists") or []:
            parts.append(lst.get("text", ""))
            parts.append(html_to_text(lst.get("content", "")))
        parts.append(j.get("additionalPlain") or "")
        yield {
            "company": name, "title": j["text"], "location": loc, "url": j.get("hostedUrl"),
            "apply_url": j.get("applyUrl"), "description": "\n".join(p for p in parts if p).strip(),
            "posted": _date(j.get("createdAt")), "employment_type": cats.get("commitment", ""),
            "source": "Lever", "ext_id": f"lv-{slug}-{j['id']}",
        }


def ashby(slug, name):
    d = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    for j in d.get("jobs", []):
        locs = [j.get("location") or ""] + [(a or {}).get("location", "") for a in j.get("secondaryLocations") or []]
        addr = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry", "")
        if not (is_india(" ".join(locs)) or is_india(addr)) or not title_passes(j.get("title", "")):
            continue
        comp = (j.get("compensation") or {}).get("compensationTierSummary")
        yield {
            "company": name, "title": j["title"], "location": j.get("location") or addr, "url": j.get("jobUrl"),
            "apply_url": j.get("applyUrl"), "description": j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            "posted": _date(j.get("publishedAt")), "employment_type": j.get("employmentType", ""),
            "salary_hint": comp, "source": "Ashby", "ext_id": f"ab-{slug}-{j['id']}",
        }


def smartrecruiters(slug, name):
    offset, seen = 0, 0
    while True:
        d = http_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?country=in&limit=100&offset={offset}")
        content = d.get("content", [])
        picked = [j for j in content if title_passes(j.get("name", ""))]

        def detail(j):
            try:
                return j, http_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j['id']}")
            except Exception:
                return j, {}

        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            for j, det in ex.map(detail, picked):
                loc = j.get("location") or {}
                loc_text = ", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x)
                secs = ((det.get("jobAd") or {}).get("sections") or {})
                desc = "\n\n".join(html_to_text((secs.get(k) or {}).get("text", "")) for k in
                                   ("companyDescription", "jobDescription", "qualifications", "additionalInformation"))
                yield {
                    "company": name, "title": j["name"], "location": loc_text or "India",
                    "url": det.get("postingUrl") or f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
                    "apply_url": det.get("applyUrl"), "description": desc.strip(), "posted": _date(j.get("releasedDate")),
                    "employment_type": (j.get("typeOfEmployment") or {}).get("label", "") + " " + (j.get("experienceLevel") or {}).get("label", ""),
                    "source": "SmartRecruiters", "ext_id": f"sr-{slug}-{j['id']}",
                }
        seen += len(content)
        offset += 100
        if not content or seen >= d.get("totalFound", 0) or offset >= 1000:
            break


def _workday_posted(text):
    """'Posted 3 Days Ago' / 'Posted Today' / 'Posted 30+ Days Ago' -> ISO date."""
    today = datetime.now(timezone.utc).date()
    if not text:
        return None
    t = text.lower()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)", t)
    return (today - timedelta(days=int(m.group(1)))).isoformat() if m else None


def workday(tenant, n, site, name):
    base = f"https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    offset, total, candidates = 0, None, []
    while total is None or offset < min(total, 1200):
        d = http_json(f"{base}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": "India"})
        total = d.get("total", 0) if total is None else total
        posts = d.get("jobPostings", [])
        if not posts:
            break
        for p in posts:
            loc = p.get("locationsText", "")
            if title_passes(p.get("title", "")) and (is_india(loc) or "location" in loc.lower()):
                candidates.append(p)
        offset += 20

    def detail(p):
        try:
            return p, http_json(base + p["externalPath"]).get("jobPostingInfo", {})
        except Exception:
            return p, None

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for p, info in ex.map(detail, candidates):
            if info is None:
                continue
            loc = p.get("locationsText", "")
            locs = " ".join([info.get("location", "")] + (info.get("additionalLocations") or []) + [loc])
            if not is_india(locs):
                continue
            yield {
                "company": name, "title": p["title"], "location": info.get("location") or loc,
                "url": info.get("externalUrl") or f"https://{tenant}.wd{n}.myworkdayjobs.com/{site}{p['externalPath']}",
                "description": html_to_text(info.get("jobDescription")),
                "posted": _date(info.get("startDate")) or _workday_posted(p.get("postedOn")),
                "employment_type": info.get("timeType", ""), "source": "Workday",
                "ext_id": f"wd-{tenant}-{p['externalPath'].rsplit('_', 1)[-1]}",
            }


def amazon():
    offset = 0
    while offset < 3000:
        d = http_json(f"https://www.amazon.jobs/en/search.json?country=IND&result_limit=100&offset={offset}&sort=recent")
        jobs = d.get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            if not title_passes(j.get("title", "")):
                continue
            desc = "\n\n".join(x for x in [
                html_to_text(j.get("description", "")),
                "Basic qualifications:\n" + html_to_text(j.get("basic_qualifications", "")),
                "Preferred qualifications:\n" + html_to_text(j.get("preferred_qualifications", "")),
            ] if x)
            yield {
                "company": "Amazon", "title": j["title"],
                "location": j.get("normalized_location") or j.get("location", ""),
                "url": "https://www.amazon.jobs" + j.get("job_path", ""), "description": desc,
                "posted": _date(j.get("posted_date")), "employment_type": j.get("job_schedule_type", "") or "",
                "source": "Amazon Jobs", "ext_id": f"amzn-{j.get('id_icims') or j.get('id')}",
            }
        offset += 100
        if offset >= d.get("hits", 0):
            break


def adzuna():
    """Aggregator covering Indian job sites. Needs free keys from developer.adzuna.com
    (set ADZUNA_APP_ID / ADZUNA_APP_KEY as repo secrets). Skipped when unset."""
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        return
    queries = ["software engineer fresher", "graduate engineer trainee", "software developer intern",
               "frontend developer", "business analyst fresher", "business development associate",
               "associate product manager", "data analyst fresher", "sde 1"]
    for q in queries:
        for page in (1, 2):
            params = urllib.parse.urlencode({"app_id": app_id, "app_key": app_key, "what": q, "salary_min": 800000,
                                             "results_per_page": 50, "max_days_old": 30, "content-type": "application/json"})
            d = http_json(f"https://api.adzuna.com/v1/api/jobs/in/search/{page}?{params}")
            for j in d.get("results", []):
                if not title_passes(j.get("title", "")):
                    continue
                lo, hi = j.get("salary_min"), j.get("salary_max")
                sal = f"₹{lo/1e5:.1f}–{hi/1e5:.1f} LPA" if lo and hi else None
                yield {
                    "company": (j.get("company") or {}).get("display_name", "Unknown"), "title": html_to_text(j["title"]),
                    "location": (j.get("location") or {}).get("display_name", "India"), "url": j.get("redirect_url"),
                    "description": html_to_text(j.get("description", "")), "posted": _date(j.get("created")),
                    "employment_type": j.get("contract_time", "") or "", "salary_hint": sal,
                    "source": "Adzuna", "ext_id": f"adz-{j.get('id')}",
                }


def atlassian():
    for j in http_json("https://www.atlassian.com/endpoint/careers/listings"):
        locs = " ".join(j.get("locations") or [])
        if not is_india(locs) or not title_passes(j.get("title", "")):
            continue
        desc = "\n\n".join(html_to_text(j.get(k, "")) for k in ("overview", "responsibilities", "qualifications"))
        portal = (j.get("portalJobPost") or {})
        yield {
            "company": "Atlassian", "title": j["title"], "location": next((l for l in j["locations"] if is_india(l)), locs),
            "url": portal.get("portalUrl") or f"https://www.atlassian.com/company/careers/details/{j['id']}",
            "description": desc.strip(), "posted": _date((portal.get("updatedDate") or "")[:10]),
            "employment_type": j.get("type", ""), "source": "Atlassian", "ext_id": f"atl-{j['id']}",
        }


# (host, site number, display name)
ORACLE_HCM = [("jpmc.fa.oraclecloud.com", "CX_1001", "JPMorgan Chase"),
              ("eeho.fa.us2.oraclecloud.com", "CX_45001", "Oracle")]


def oracle_hcm(host, site, name):
    api = f"https://{host}/hcmRestApi/resources/latest"
    offset = 0
    while offset < 2000:
        d = http_json(f"{api}/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations"
                      f"&finder=findReqs;siteNumber={site},keyword=India,limit=100,offset={offset}")
        block = (d.get("items") or [{}])[0]
        reqs = block.get("requisitionList") or []
        for r in reqs:
            if r.get("PrimaryLocationCountry") != "IN" or not title_passes(r.get("Title", "")):
                continue
            try:
                det = http_json(f"{api}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
                                f"&finder=ById;Id=%22{r['Id']}%22,siteNumber={site}")["items"][0]
            except Exception:
                det = {}
            desc = "\n\n".join(html_to_text(det.get(k) or "") for k in
                               ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))
            yield {
                "company": name, "title": r["Title"], "location": r.get("PrimaryLocation", "India"),
                "url": f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{r['Id']}",
                "description": desc.strip(), "posted": _date(r.get("PostedDate")),
                "employment_type": r.get("WorkerType") or "", "source": "Oracle HCM", "ext_id": f"ohcm-{host}-{r['Id']}",
            }
        offset += 100
        if not reqs or offset >= block.get("TotalJobsCount", 0):
            break


def google():
    """Google's careers page filtered to early-career + intern roles in India (data embedded in the HTML)."""
    page = 1
    while page <= 10:
        url = ("https://www.google.com/about/careers/applications/jobs/results/"
               f"?location=India&target_level=EARLY&target_level=INTERN_AND_APPRENTICE&page={page}")
        req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode("utf-8", "ignore")
        m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", body, re.S)
        if not m:
            break
        data = json.loads(m.group(1))
        jobs = data[0] or []
        for j in jobs:
            title = j[1]
            locs = "; ".join(l[0] for l in (j[9] or []) if l)
            if not is_india(locs) or not title_passes(title):
                continue
            text = lambda i: html_to_text((j[i] or [None, ""])[1] if len(j) > i else "")
            desc = "\n\n".join(x for x in [text(10), "Responsibilities:\n" + text(3), "Qualifications:\n" + text(4)] if x)
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            posted = j[12][0] * 1000 if len(j) > 12 and j[12] else None
            yield {
                "company": j[7] or "Google", "title": title, "location": locs,
                "url": f"https://www.google.com/about/careers/applications/jobs/results/{j[0]}-{slug}",
                "apply_url": j[2], "description": desc, "posted": _date(posted), "employment_type": "",
                "source": "Google Careers", "ext_id": f"goog-{j[0]}",
            }
        total = data[2] or 0
        if page * 20 >= total:
            break
        page += 1
