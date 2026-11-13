---
description: Execute a Teammate A task (Core Pipeline, Pre-Flight, Resume/Gap AI & Apply)
---
# Workflow: Work as Teammate A (Core Pipeline & Apply)

1. Run `.agent/workflows/01-sync-board.md` first.
2. Read `plans/OWNER_A_WORKBOOK.md` and `plans/DIFFERENTIATORS_SPEC.md` (`D1`, `D2`, `D3`, `D5`).
3. Confirm you only edit Owner A modules (`app/engine.py`, `app/routes_pipeline.py`, `web/pipeline.js`, Owner A adapters/tests) unless an approved ADR in `comms/decisions/` authorizes a shared contract change.
4. Keep every real-vs-demo boundary honest (`test_submitted` vs `confirmed`, explicit approval before submit, SHA-256 receipts, never guess sensitive eligibility answers).
5. Run verification:
   - `python3 -m unittest discover -s tests -v`
   - `python3 scripts/validate_package.py`
6. Update `comms/BOARD.md`, release your file lock, and write a handoff file in `comms/handoffs/` if Owner B consumes your output (e.g., `CallbackPacket` or `ModelAdapter`).
