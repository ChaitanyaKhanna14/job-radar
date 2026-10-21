# Job Radar

Fresher jobs and internships in India from companies that pay ≥ 8 LPA, refreshed every morning before 8 AM IST and shown on a mobile-friendly GitHub Pages site with an "applied" tick for each job.

## How it works

- `scraper/` runs daily in GitHub Actions (`.github/workflows/daily.yml`). It reads the official public job-board APIs of ~100 companies (Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Oracle HCM, Amazon, Google, Atlassian), plus Adzuna if you add keys. Then it keeps only roles that:
  - are in India (or remote-India),
  - are internships or entry-level (title signals like Intern / Graduate / SDE-1 / Associate, or a JD asking for 0–1 years; anything that asks for 2+ years is dropped),
  - fall under Engineering, Analyst, Business/BD or Product,
  - and aren't low-paying ops/support roles. If a JD states a salary under 8 LPA, the role is dropped.
- `docs/` is the site. `docs/data/jobs.json` holds the list. `docs/data/applied.json` holds the ticks, which sync across devices through the GitHub API once you add a token in the site's ⚙ settings.
- `tools/tailor.py` writes a tailored resume for each JD to `../private/tailored/` (outside this public repo).

## Pay filter

Most postings don't publish salary. The ≥ 8 LPA rule is enforced mainly by which companies are scanned (`scraper/companies.py`), and by dropping any JD that states a lower figure. Edit that file to add or remove companies.

## Optional: Adzuna aggregator

Get free keys at <https://developer.adzuna.com>, then add repo secrets `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. The aggregator searches Indian job sites with a ₹8 L minimum salary.

## Run locally

```bash
cd scraper && python run.py
```
