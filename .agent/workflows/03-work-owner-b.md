---
description: Execute a Teammate B task (Artifact Contacts, Outreach, Inbox Tracking & Portability)
---
# Workflow: Work as Teammate B (Networking, Inbox & Portability)

1. Run `.agent/workflows/01-sync-board.md` first.
2. Read `plans/OWNER_B_WORKBOOK.md` and `plans/DIFFERENTIATORS_SPEC.md` (`D4`, plus `D2` callback trigger UI).
3. Confirm you only edit Owner B modules (`app/routes_outreach.py`, `web/outreach.js`, `skills/`, `prompts/`, `deliverables/`, Owner B adapters/tests) unless an approved ADR in `comms/decisions/` authorizes a shared contract change.
4. Enforce security rules: no LinkedIn scraping, no guessed emails, explicit approval before sending, per-company cooldowns, instant opt-out enforcement, and prompt-injection boundaries on inbox bodies.
5. Whenever modifying `skills/*/SKILL.md`, run `python3 scripts/sync_harness.py`.
6. Run verification:
   - `python3 scripts/sync_harness.py --check`
   - `python3 -m unittest discover -s tests -v`
   - `python3 scripts/validate_package.py`
7. Update `comms/BOARD.md`, release your file lock, and file a handoff ticket in `comms/handoffs/` when ready for cross-review.
