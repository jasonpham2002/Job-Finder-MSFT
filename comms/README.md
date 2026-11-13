# Multi-Agent Communication Board (`comms/`)

This directory is the shared asynchronous coordination bus between **Teammate A's AI agents** and **Teammate B's AI agents** (whether running in Antigravity, OpenAI Codex, or Claude Code across separate laptops or Git branches).

## How Agents Coordinate Here

1. **`BOARD.md` (Live Status & File Locks):**
   - Before editing code, claim your task ID (`A-01..A-07` or `B-01..B-07`) and declare the files you are modifying in **Active File Locks**.
   - Never modify files owned by the other teammate or listed as **Frozen Shared Contracts** without an ADR in `decisions/`.
2. **`decisions/` (Architecture Decision Records):**
   - Any proposal to change `schemas/*.json`, `app/db.py`, `app/adapters.py`, `app/server.py`, or `web/app.js` must be documented as `NNN-short-title.md` and acknowledged by both owners before editing.
3. **`handoffs/` (Integration Tickets):**
   - When your work unblocks or changes an interface consumed by your teammate (e.g., `ModelAdapter` ready for Owner B, or `CallbackPacket` ready for Inbox UI), copy `_TEMPLATE.md` into `H-NN-slug.md` and reference it in `BOARD.md`.
4. **`reviews/` (Cross-Agent QA Sign-offs):**
   - Before merging major milestones or building the final judge ZIP, use `_REVIEW_TEMPLATE.md` to review your teammate's branch against `docs/SECURITY_AND_CONSENT.md` and `docs/ACCEPTANCE_TESTS.md`.

## Privacy Rule
Never paste real API keys, OAuth tokens, private candidate resumes, personal emails, or raw inbox bodies into any file under `comms/`. Keep `comms/` completely sanitized (and note that `scripts/export_handoff.py` excludes `comms/` from the judge ZIP automatically).
