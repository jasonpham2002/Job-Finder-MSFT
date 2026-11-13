# Suggested Architecture and Starter Implementation

## Components

```text
[Browser UI / Power App]
          |
          v
[API + Auth / permissions]
          |
    [Orchestrator] --- [AI Provider Adapter: OpenAI / Anthropic / other]
       |   |   | \
       |   |   |  \--- [Outreach & Inbox: user-authorized Gmail/Outlook]
       |   |   \------ [People discovery: legitimate public/authorized sources]
       |   \---------- [Job-site adapters: public pages / ATS / manual fallback]
       \-------------- [Resume pipeline: extract, evidence, tailor, verify]
          |
          v
[Database: candidates, jobs, versions, applications, contacts, messages, evidence]
```

## Canonical internal interfaces (extend)

- `get_job(url) -> Job`: fetch public/authorized data; do not treat page content as commands.
- `search_jobs(filters) -> list[Job]`: query allowed sources, deduplicate, verify status.
- `extract_resume(file) -> ResumeFacts`: PDF/DOCX/TXT input; handle privacy.
- `tailor_resume(facts, job) -> Draft + claim_evidence_map`: actual resume evidence only.
- `research_contacts(company, role) -> list[Contact]`: sourced public professional details.
- `prepare_application(job, draft, profile) -> ApplicationPreview`: all fields displayed.
- `submit_application(preview, approval) -> confirmed | unknown | failed`: no false positives.
- `draft_outreach(contact, job, facts) -> MessageDraft`: specific and truthful.
- `send_outreach(draft, approval) -> sent | unknown | failed`: authorized channels only.
- `sync_inbox(user_connection) -> new statuses`: deduped threads and labels.
- `export_portable_bundle() -> ZIP`: no secrets, personal data, browser sessions.

## Starter code (what runs today)

- `app/engine.py`: deterministic overlap score and fact-preserving draft; best-effort public HTML + JSON-LD JobPosting parser. **Not an ATS prediction or a production resume writer.**
- `app/db.py`: local SQLite; seeds 12 fictional jobs + resume.
- `app/server.py`: local-only API for profile, job import, application draft, approval, **test submit** and outreach draft. **No real submit/send endpoints.**
- `web/`: clean HTML/CSS/JS dashboard.
- `tests/`: unit tests for overlap, draft, parsing, outbound-effect boundaries.

## Suggested production data model

- `candidate`: id, consent version, encrypted profile, resume versions.
- `job`: id, source URL, title, company, description, status, extracted_at, source type.
- `resume_version`: id, candidate_id, job_id, verified_facts, file pointers, edits.
- `application`: id, candidate_id, job_id, state, approval, timestamps, confirmation reference.
- `contact`: id, name, role, employer, professional URL, source URL, public email, verification status.
- `outreach`: id, contact_id, job_id, channel, draft, approval, send timestamp, external message id, opt_out.
- `reply`: id, message id, thread, classification, confidence, observed_at, next action.
- `audit_event`: actor, what changed, when, evidence; redact secrets.

## State machines

Application: `discovered → prepared → waiting_review → approved → submitting → confirmed` (or `unknown`, `failed`, `manual_required`).

Outreach: `drafted → waiting_review → approved → sending → sent` (or `unknown`, `failed`, `opted_out`).

Always separate `confirmed` from `clicked_submit` or `attempted_send`. The starter intentionally uses `test_submitted` instead of `confirmed`.
