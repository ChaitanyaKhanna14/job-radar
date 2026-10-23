"""Daily scrape: fetch every source, keep India fresher roles, merge with yesterday's list,
write docs/data/jobs.json for the site."""
import concurrent.futures as cf
import hashlib
import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import companies as C
import sources as S
from filters import classify

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
JOBS_FILE = DATA / "jobs.json"
APPLIED_FILE = DATA / "applied.json"
IST = timezone(timedelta(hours=5, minutes=30))
MAX_DESC = 6000
STALE_DAYS = 60  # drop postings older than this (by posted date) unless applied


def tasks():
    for slug, name in C.GREENHOUSE.items():
        yield name, "greenhouse", lambda s=slug, n=name: S.greenhouse(s, n)
    for slug, name in C.LEVER.items():
        yield name, "lever", lambda s=slug, n=name: S.lever(s, n)
    for slug, name in C.ASHBY.items():
        yield name, "ashby", lambda s=slug, n=name: S.ashby(s, n)
    for slug, name in C.SMARTRECRUITERS.items():
        yield name, "smartrecruiters", lambda s=slug, n=name: S.smartrecruiters(s, n)
    for tenant, n, site, name in C.WORKDAY:
        yield name, "workday", lambda t=tenant, k=n, s=site, nm=name: S.workday(t, k, s, nm)
    for host, site, name in S.ORACLE_HCM:
        yield name, "oracle", lambda h=host, s=site, n=name: S.oracle_hcm(h, s, n)
    yield "Amazon", "amazon", S.amazon
    yield "Atlassian", "atlassian", S.atlassian
    yield "Google", "google", S.google
    yield "Unstop (platform)", "unstop", S.unstop
    yield "Adzuna (aggregator)", "adzuna", S.adzuna


def run_one(label, kind, fn):
    out = []
    for raw in fn():
        verdict = classify(raw["title"], raw.get("description", ""), raw.get("employment_type", ""), lenient=kind in ("adzuna", "unstop"))
        if not verdict:
            continue
        sal = raw.get("salary_hint") or verdict["salary"]
        out.append({
            "id": hashlib.sha1(raw["ext_id"].encode()).hexdigest()[:12],
            "company": raw["company"], "title": raw["title"].strip(), "location": raw.get("location", ""),
            "type": verdict["type"], "category": verdict["category"], "salary": sal,
            "posted": raw.get("posted"), "source": raw["source"],
            "url": raw.get("url"), "apply_url": raw.get("apply_url") or raw.get("url"),
            "description": (raw.get("description") or "")[:MAX_DESC],
        })
    return out


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    today = datetime.now(IST).date().isoformat()
    prev = load(JOBS_FILE, {"jobs": []})
    prev_by_id = {j["id"]: j for j in prev.get("jobs", [])}
    applied = load(APPLIED_FILE, {})

    fresh, status, failed = {}, {}, set()
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(run_one, label, kind, fn): label for label, kind, fn in tasks()}
        for fut in cf.as_completed(futs):
            label = futs[fut]
            try:
                jobs = fut.result()
                status[label] = len(jobs)
                for j in jobs:
                    fresh[j["id"]] = j
            except Exception as e:
                status[label] = f"error: {type(e).__name__}: {str(e)[:120]}"
                failed.add(label)
                traceback.print_exc(file=sys.stderr)

    by_key = {}
    for j in sorted(fresh.values(), key=lambda j: j.get("posted") or "", reverse=True):
        by_key.setdefault((j["company"].lower(), j["title"].lower(), j["location"].lower()), j)
    fresh = {j["id"]: j for j in by_key.values()}

    cutoff = (datetime.now(IST).date() - timedelta(days=STALE_DAYS)).isoformat()
    merged = {}
    for jid, j in fresh.items():
        old = prev_by_id.get(jid)
        j["first_seen"] = old["first_seen"] if old else today
        if j.get("posted") and j["posted"] < cutoff and jid not in applied:
            continue
        merged[jid] = j
    for jid, old in prev_by_id.items():
        if jid in merged:
            continue
        if old["company"] in failed:  # source was down today; keep yesterday's copy
            merged[jid] = old
        elif jid in applied:
            old["closed"] = True
            merged[jid] = old

    jobs = sorted(merged.values(), key=lambda j: (j["first_seen"], j.get("posted") or ""), reverse=True)
    DATA.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps({
        "updated_at": datetime.now(IST).isoformat(timespec="minutes"),
        "count": len(jobs),
        "new_today": sum(1 for j in jobs if j["first_seen"] == today),
        "sources": dict(sorted(status.items())),
        "jobs": jobs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    if not APPLIED_FILE.exists():
        APPLIED_FILE.write_text("{}\n", encoding="utf-8")

    print(f"{len(jobs)} jobs ({sum(1 for j in jobs if j['first_seen'] == today)} new) from {len(status)} sources; {len(failed)} failed")
    for k, v in sorted(status.items(), key=lambda kv: str(kv[1])):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
