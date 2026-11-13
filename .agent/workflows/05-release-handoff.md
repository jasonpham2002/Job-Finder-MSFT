---
description: Prepare and validate the clean portable hackathon submission ZIP
---
# Workflow: Release & Judge Handoff Check

1. Ensure `.env`, `local_demo.sqlite3`, real resumes, and OAuth tokens are NOT present in the export tree.
2. Confirm `deliverables/TEAM_HANDOFF_TEMPLATE.md` accurately lists real vs. test/manual counts (`0-10`), required env var names only, and known limitations.
3. Run:
   - `python3 scripts/sync_harness.py --check`
   - `python3 -m unittest discover -s tests -v`
   - `python3 scripts/validate_package.py`
   - `python3 scripts/export_skills.py`
   - `python3 scripts/export_handoff.py`
4. Inspect `exports/jobfinder-complete-portable-handoff.zip` to confirm `comms/`, `plans/`, `.codex/`, `.agent/`, `.agents/`, `CLAUDE.md`, `.env`, and `.sqlite3` are excluded while `app/`, `web/`, `skills/`, `prompts/`, `schemas/`, `scripts/`, `tests/`, and `docs/` are clean and runnable on Computer B.
