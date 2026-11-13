# ADR 000: Multi-Agent Architecture, Stack & Contract Boundaries

- **Date:** 2026-11-13
- **Status:** Accepted
- **Participants:** Teammate A, Teammate B

## Context
We are a 2-person team building Hackathon Challenge 4 within a 4–6 hour sprint using AI coding harnesses (Antigravity and OpenAI Codex). We need robust live adapters, all 5 differentiators (`D1`–`D5`), clean portability to a judge's second computer ("Computer B"), and zero parallel merge conflicts.

## Decisions
1. **Runtime Stack:** Keep Python 3.10+ standard HTTP server (`app/server.py`), SQLite (`app/db.py`), and vanilla HTML/CSS/JS (`web/`), adding only lightweight `pip` libraries for PDF/DOCX extraction, LLM SDKs, email OAuth, and optional Playwright HITL.
2. **LLM Provider Abstraction:** Support OpenAI (`OPENAI_API_KEY`), Google Gemini (`GEMINI_API_KEY`), and Anthropic (`ANTHROPIC_API_KEY`) behind one `ModelAdapter` interface (`config.llm_provider = "auto"`).
3. **Email Integration:** Implement Gmail desktop OAuth as primary (`GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`), maintain a compatible Microsoft Graph/Outlook contract (`OUTLOOK_CLIENT_ID`), and preserve manual draft fallback.
4. **Application Submission Strategy (Hybrid):** Use permitted public ATS feeds (`Greenhouse`, `Lever`, `Ashby`) for discovery, a universal **Co-Pilot Copy-Paste Packet** with hard-locked sensitive fields + SHA-256 receipts (`D3`) for reliable cross-portal submissions (including Workday), and optional headed Playwright human-in-the-loop autofill (`enable_playwright_hitl`). Never bypass logins, CAPTCHAs, or LinkedIn restrictions.
5. **Vertical Team Split & Conflict-Free Module Seams:**
   - `app/server.py` and `web/app.js` stay frozen thin entrypoints delegating to `app/routes_pipeline.py` + `web/pipeline.js` (Owner A) and `app/routes_outreach.py` + `web/outreach.js` (Owner B).
   - Shared contracts (`schemas/*.json`, `app/db.py`, `app/adapters.py`) are frozen upfront and changed only via a new ADR here.
6. **Git vs. Judge Export Boundary:** `plans/`, `comms/`, `.codex/`, `.agent/`, `.agents/`, and `CLAUDE.md` are committed to Git for cross-laptop collaboration, while `scripts/export_handoff.py` excludes them from `exports/jobfinder-complete-portable-handoff.zip` so the judge archive contains only clean app code, docs, schemas, tests, and canonical `skills/`.

## Consequences
- Both teammates' agents can begin `A-01` and `B-01` simultaneously right after Phase 0 without file collisions.
- `scripts/sync_harness.py` keeps `.agents/skills/` synchronized with `skills/*/SKILL.md` for Codex without symlinks.
