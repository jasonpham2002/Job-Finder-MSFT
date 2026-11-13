# Two-Person Team Charter & File Ownership

## Purpose
This charter eliminates merge conflicts and ambiguity when **two teammates** build simultaneously using **Antigravity** and **OpenAI Codex**. Every file has one clear owner or is locked behind a shared contract protocol.

## Roles & Workscopes

| Role | Primary Focus | End-to-End Scope | Differentiators Owned |
|---|---|---|---|
| **Teammate A (Owner A)** | Core Pipeline, AI Tailoring & Apply | Job discovery & URL intake, Ghost/Scam Pre-Flight, PDF/DOCX extraction, unified `ModelAdapter` (OpenAI/Gemini/Anthropic), Anti-Slop tailoring + ATS preview, Gap-to-Proof Bridge, Co-Pilot + optional Playwright HITL + Receipts | **D1, D2, D3, D5** |
| **Teammate B (Owner B)** | Networking, Outreach, Inbox & Portability | Artifact-first public contact discovery, Gmail primary + Outlook `OutreachAdapter`, Cooldown & Opt-Out Firewall, `InboxAdapter` reply classifier + Callback Trigger UI, tracking dashboard enhancements, `skills/` + `prompts/` upgrades, Computer B portability & QA | **D4**, plus **D2 Callback Trigger UI** & **Portability** |

## Strict File Ownership Matrix

### Owner A Exclusive Write Zone
- `app/engine.py`
- `app/routes_pipeline.py`
- `app/adapters_pipeline.py` *(recommended new file for Owner A adapter implementations)*
- `web/pipeline.js`
- `tests/test_pipeline.py` *(recommended new test file for Owner A)*

### Owner B Exclusive Write Zone
- `app/routes_outreach.py`
- `app/adapters_outreach.py` *(recommended new file for Owner B adapter implementations)*
- `web/outreach.js`
- `skills/*/SKILL.md` *(and `.agents/skills/` via `python3 scripts/sync_harness.py`)*
- `prompts/*.md`
- `deliverables/TEAM_HANDOFF_TEMPLATE.md`
- `tests/test_outreach.py` *(recommended new test file for Owner B)*

### Frozen Shared Contracts (RFC Required via `comms/decisions/`)
Do **not** modify these files without posting a Decision Record in `comms/decisions/` or acquiring an explicit lock in `comms/BOARD.md`:
- `schemas/*.json`
- `app/db.py`
- `app/adapters.py`
- `app/server.py`
- `web/index.html`, `web/app.js`, `web/styles.css`
- `scripts/validate_package.py`, `scripts/export_handoff.py`, `scripts/export_skills.py`
- `AGENTS.md`, `CLAUDE.md`, `.codex/config.toml`

## How Owner A & Owner B Connect (Integration Boundaries)

1. **Job → Contact Handoff (`jobs` table + `schemas/job.schema.json`):**
   - Owner A normalizes imported/discovered jobs and writes `ats_family` and `preflight_json`.
   - Owner B reads `jobs.company`, `jobs.title`, `jobs.url`, and `jobs.description` to research artifact-verified contacts without re-scraping blocked job boards.
2. **Tailoring → Callback Cheat Sheet (`applications` table):**
   - Owner A populates `applications.callback_packet_json` (`tailored_diff`, `answers_json`, `probe_questions`, `resume_sha256`).
   - Owner B's `InboxAdapter` classifies incoming email replies (`human_positive_reply`, `interview_invitation`, etc.), matches the application by `company`/`job_id`, and surfaces Owner A's `callback_packet_json` directly next to the reply in the dashboard.
3. **Model & Resume Evidence Reuse:**
   - Owner A implements `ModelAdapter` cleanly in `app/adapters_pipeline.py` (following `app/adapters.py`) so Owner B can call `ModelAdapter.generate(...)` for outreach drafting and reply classification without duplicating OpenAI/Gemini/Anthropic SDK boilerplate.

## Git & Agent Coordination Workflow
- Branch naming: `feat/a-<task-id>-<slug>` (Owner A), `feat/b-<task-id>-<slug>` (Owner B).
- Merge to `main` frequently (every 45–60 minutes) after running tests + updating `comms/BOARD.md`.
- Never commit `.env`, `local_demo.sqlite3`, real candidate resumes, or OAuth tokens.
