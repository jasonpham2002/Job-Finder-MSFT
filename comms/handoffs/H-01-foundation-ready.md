# Handoff Ticket: H-01 — Shared Multi-Agent Foundation Ready

- **From:** Shared Setup (`S-01`)
- **To:** Owner A & Owner B
- **Related Task ID:** `S-01`
- **Date:** 2026-11-13

## Contract / Interface Exposed
- **Schemas (`schemas/`):** Upgraded `job.schema.json`, `application.schema.json`, `contact.schema.json`, and added `gap_artifact.schema.json`.
- **Database (`app/db.py`):** Idempotent migrations adding `jobs` preflight/ATS columns, `applications` claim-map/slop/ATS-preview/answers/callback-packet/receipt columns, plus `contacts`, `replies`, `gap_artifacts`, and `audit_events` tables.
- **Adapters (`app/adapters.py`):** Typed dataclasses (`JobPreflight`, `TailoredResumeResult`, `GapAnalysisResult`, `CoPilotPacket`, `ApplicationReceipt`, `VerifiedContact`, `InboxReply`) and abstract method contracts for all 7 adapters.
- **Modular Seams:**
  - Owner A owns `app/routes_pipeline.py` (mounted at `/api/pipeline/*`) and `web/pipeline.js` (`#pipelineExtensions`).
  - Owner B owns `app/routes_outreach.py` (mounted at `/api/networking/*`, `/api/inbox/*`) and `web/outreach.js` (`#outreachExtensions`).

## Action Needed by Receiving Teammates
1. **Owner A:** Claim `A-01` in `comms/BOARD.md`, implement `ModelAdapter` + `ResumeFileAdapter` in `app/adapters_pipeline.py`, and post handoff `H-02` when `ModelAdapter` is ready for Owner B.
2. **Owner B:** Claim `B-01` in `comms/BOARD.md` in parallel and implement Gmail OAuth + Outlook contract in `app/adapters_outreach.py` (initially with deterministic fallback until `H-02` lands).
