"""Tailor your resume to a job description and save it as HTML + PDF.

Everything personal lives in ../../private (outside this public repo):
    private/resume.md       your master resume (the source of truth; nothing is invented beyond it)
    private/profile.json    form details (name, phone, links, CGPA, ...)
    private/tailored/       output, one folder per job

Usage:
    python tailor.py auto --job <id> [--job <id> ...]   # needs ANTHROPIC_API_KEY and `pip install anthropic`
    python tailor.py auto --new --limit 10               # today's new, not-yet-applied jobs
    python tailor.py render <folder>                      # re-render resume.html -> resume.pdf
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRIVATE = Path(os.environ.get("JOB_RADAR_PRIVATE", REPO.parent / "private"))
OUT = PRIVATE / "tailored"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

PRINT_CSS = """
@page { size: A4; margin: 9mm 12mm; }
* { box-sizing: border-box; }
body { font: 10pt/1.3 "Calibri", "Segoe UI", Arial, sans-serif; color: #111; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 2px; letter-spacing: .2px; }
.contact { font-size: 9.5pt; color: #333; margin-bottom: 4px; }
.where { font-weight: 400; font-style: italic; color: #444; }
.contact a { color: #111; text-decoration: none; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: .8px; border-bottom: 1.2px solid #111; padding-bottom: 1px; margin: 7px 0 3px; }
h3 { font-size: 10pt; margin: 4px 0 1px; display: flex; justify-content: space-between; gap: 8px; }
h3 .when { font-weight: 400; color: #333; white-space: nowrap; }
.sub { font-style: italic; color: #333; margin: 0 0 2px; }
ul { margin: 1px 0 2px 16px; padding: 0; }
li { margin: 0 0 1.5px; }
p { margin: 2px 0; }
.skills p { margin: 1px 0; }
"""

SYSTEM = """You tailor a candidate's resume to one job description.

Hard rules:
- Use only facts present in the master resume. Never invent employers, dates, projects, metrics, tools, degrees or skills.
  You may rephrase bullets, reorder sections and bullets, merge or drop weaker items, and surface relevant skills that the
  resume already supports.
- Mirror the job description's wording where the candidate genuinely has that experience, so ATS keyword matching works.
- One A4 page. Plain, ATS-safe structure: no tables, columns, icons or images.
- Section order: Summary (2 lines, specific to this role), Education, Experience, Projects, Skills, then anything else
  (achievements, certifications, positions of responsibility) only if relevant.

Output exactly two blocks and nothing else:
<resume_html>
...body HTML only, using: <h1> name, <div class="contact"> contact line, <h2> section headings,
<h3>Role, Company<span class="when">Dates</span></h3>, <p class="sub"> for a subtitle, <ul><li> bullets,
<div class="skills"><p><b>Label:</b> items</p></div> for skills...
</resume_html>
<notes>
Match score 0-100, the JD keywords covered, important JD requirements the resume can't honestly claim, and a
2-3 sentence answer the candidate could paste for "Why are you interested in this role?".
</notes>"""


def slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def load_jobs():
    return {j["id"]: j for j in json.loads((REPO / "docs/data/jobs.json").read_text(encoding="utf-8"))["jobs"]}


def job_dir(job):
    return OUT / f"{slug(job['company'], 25)}_{slug(job['title'])}_{job['id']}"


def find_browser():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(p).exists():
            return p
    return shutil.which("msedge") or shutil.which("google-chrome") or shutil.which("chromium")


def write_html(folder, body_html, title):
    folder.mkdir(parents=True, exist_ok=True)
    html = f'<!doctype html><html><head><meta charset="utf-8"><title>{title}</title><style>{PRINT_CSS}</style></head><body>{body_html}</body></html>'
    (folder / "resume.html").write_text(html, encoding="utf-8")


def render(folder):
    folder = Path(folder)
    browser = find_browser()
    if not browser:
        print("No Edge/Chrome found; open resume.html and print to PDF manually.")
        return None
    pdf = folder / "resume.pdf"
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", (folder / "resume.html").resolve().as_uri()],
                   check=True, capture_output=True, timeout=120)
    return pdf


def tailor_with_api(job, resume_md, profile):
    import anthropic  # pip install anthropic

    client = anthropic.Anthropic()
    user = (f"<master_resume>\n{resume_md}\n</master_resume>\n\n"
            f"<candidate_profile>\n{json.dumps(profile, indent=1)}\n</candidate_profile>\n\n"
            f"<job>\nCompany: {job['company']}\nTitle: {job['title']}\nLocation: {job['location']}\n\n"
            f"{job['description']}\n</job>")
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Model declined this request")
    text = "".join(b.text for b in resp.content if b.type == "text")
    body = re.search(r"<resume_html>(.*?)</resume_html>", text, re.S)
    notes = re.search(r"<notes>(.*?)</notes>", text, re.S)
    if not body:
        raise RuntimeError("Response had no <resume_html> block")
    return body.group(1).strip(), (notes.group(1).strip() if notes else "")


def cmd_auto(args):
    resume_md = (PRIVATE / "resume.md").read_text(encoding="utf-8")
    profile_path = PRIVATE / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    jobs = load_jobs()
    if args.new:
        applied = json.loads((REPO / "docs/data/applied.json").read_text(encoding="utf-8"))
        today = max(j["first_seen"] for j in jobs.values())
        ids = [i for i, j in jobs.items() if j["first_seen"] == today and i not in applied][: args.limit]
    else:
        ids = args.job
    for jid in ids:
        job = jobs.get(jid)
        if not job:
            print(f"skip {jid}: not in jobs.json")
            continue
        folder = job_dir(job)
        if (folder / "resume.pdf").exists() and not args.force:
            print(f"exists {folder.name}")
            continue
        body, notes = tailor_with_api(job, resume_md, profile)
        write_html(folder, body, f"{profile.get('name', 'Resume')} - {job['company']}")
        (folder / "notes.md").write_text(f"# {job['title']} @ {job['company']}\n{job['apply_url']}\n\n{notes}\n", encoding="utf-8")
        (folder / "job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
        pdf = render(folder)
        print(f"done {folder.name} -> {pdf or folder / 'resume.html'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auto")
    a.add_argument("--job", action="append", default=[])
    a.add_argument("--new", action="store_true")
    a.add_argument("--limit", type=int, default=10)
    a.add_argument("--force", action="store_true")
    r = sub.add_parser("render")
    r.add_argument("folder")
    args = ap.parse_args()
    if args.cmd == "auto":
        cmd_auto(args)
    else:
        print(render(args.folder))


if __name__ == "__main__":
    sys.exit(main())
