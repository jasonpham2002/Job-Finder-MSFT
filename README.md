# Hackathon 4 — Universal Job Finder, Auto Apply & Networking Agent

**Student-ready challenge and runnable local starter — November 2026**

The goal: using a resume plus **any job posting URL** (LinkedIn, Indeed, Workday, Greenhouse, Lever, an employer careers page, etc.), create a reusable AI agent that analyzes roles, tailors truthful resumes, finds relevant professional contacts, prepares approved outreach, applies to **10 real jobs** where authorized, tracks results, and can be exported to another computer or AI system.

> **Read this first:** `START_HERE_STUDENTS.md`. The ZIP contains a working **offline demo scaffold**, not a finished auto-apply bot. The starter does NOT search live listings, sign in to job boards, submit real applications, scrape LinkedIn, send messages, or monitor real inboxes. These are the student implementation tasks. Demo successes are clearly labeled and cannot be counted as real submissions.

## Run the starter (no Python packages needed)

1. Install Python 3.10+.
2. Extract this entire ZIP into a normal folder.
3. Open a terminal in that folder.
4. Run: `python -m app.server` (Windows may use `py -m app.server`).
5. Open **http://127.0.0.1:8765**.
6. The dashboard loads 12 **fictional** jobs and one **fictional** resume. Import an external public job URL, or paste the job description if the site blocks access.
7. To stop, press Ctrl+C. The local SQLite database is saved at `local_demo.sqlite3` and is intentionally excluded from exports.

Convenience launchers: `scripts/run_windows.bat` or `scripts/run_mac_linux.sh`.

## Package map

- `START_HERE_STUDENTS.md` — student onboarding, scope and rules.
- `CHALLENGE_BRIEF.md` — exact required end-to-end challenge.
- `docs/RUBRIC.md` — scoring, bonuses, evidence standards.
- `docs/ACCEPTANCE_TESTS.md` — mandatory live judge tests.
- `docs/BUILD_PLAN.md` — recommended 4–6 hour development sequence.
- `docs/ARCHITECTURE.md` — suggested modules and data model.
- `docs/INTEGRATION_GUIDE.md` — real job-site and outreach adapters.
- `docs/SECURITY_AND_CONSENT.md` — privacy, safety and platform compliance.
- `docs/PORTABILITY_GUIDE.md` — transfers across computers and AI providers.
- `docs/DEMO_SCRIPT.md` — demo and judging checklist.
- `skills/*/SKILL.md` — six portable, open-format agent skills.
- `prompts/*` — system, research, resume, outreach and response prompts.
- `schemas/*.json` — normalized data contracts / example config.
- `sample_data/` — synthetic resume, 12 job postings, contacts and inbox examples.
- `app/` and `web/` — **running standard-library Python + SQLite + HTML/JS demo scaffold**.
- `scripts/` — run, skill export and package checks.
- `tests/` — automated tests using Python built-in `unittest`.
- `deliverables/TEAM_HANDOFF_TEMPLATE.md` — handoff file students must complete.

## Test & export

```bash
python -m unittest discover -s tests -v
python scripts/validate_package.py
python scripts/export_skills.py
python scripts/export_handoff.py
```

The skill command creates **six individual skill ZIPs** plus an **all-skills bundle** under `exports/`. The handoff command packages the complete source code, documents and ready-to-import skills into a clean portable ZIP, excluding local databases and secrets. Never place passwords, keys, tokens, real resumes, browser cookies, or contact databases in shared exports.

## Not universal automation by magic

A job URL is a starting point, not permission to bypass a site's logins, CAPTCHAs, robots restrictions or terms. Some URLs cannot be fetched automatically. The judge should test a previously unseen URL and observe an honest fallback to a pasted job description. Individual sites may require approved connectors, authenticated user actions, or manual submission.

## External documentation

- Agent Skills specification: https://agentskills.io/specification
- Claude custom skills: https://support.claude.com/en/articles/12512180-use-skills-in-claude
- ChatGPT skills: https://help.openai.com/en/articles/20001066-skills-in-chatgpt
- LinkedIn automated activity guidance: https://www.linkedin.com/help/learning/answer/a1340567

**Students:** The scaffold is a reference implementation and can be replaced. Your final deliverable must be runnable by another person, not merely work in your own AI chat session.
