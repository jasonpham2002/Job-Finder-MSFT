# Handoff H-03 — Gap-to-Proof Bridge (D5) & 30-Second Callback Cheat Sheet (`callback_packet_json`, D2)

**From:** Owner A (`A-05`)  
**To:** Owner B (`B-04` InboxAdapter + Callback Trigger UI + Tracking Dashboard)  
**Status:** Ready (pending final test pass check)  
**Branch:** `feat/a-05-gap-proof-callback`

---

## What Was Built (A-05)

1. **D5 Gap-to-Proof Bridge (`app/engine.py`, `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`):**
   - `GapBridgeAdapter` separates missing role keywords into:
     - `wording_gap` (`gap_artifacts.gap_type = 'wording_gap'`, `verified = 0`): candidate already possesses overlapping/synonymous experience backed verbatim in the uploaded/profile resume (`job_term`, `candidate_evidence`).
     - `true_skill_gap` (`gap_artifacts.gap_type = 'true_skill_gap'`, `verified = 0` until proven): genuinely missing skill with a scoped **48-hour `micro_project_brief`**. Remains blocked from `VoicePreservingTailorAdapter` / `/api/pipeline/prepare-ai` until the candidate submits a valid public `https://`/`http://` `proof_url` via `POST /api/pipeline/gaps/<id>/verify`.
   - Verified `true_skill_gap` rows (`verified = 1`, `proof_url` validated against private/loopback/SSRF ranges via `engine.valid_public_url`) automatically unlock those skills for subsequent `/api/pipeline/prepare-ai` tailoring and populate `verified_gap_proofs` + targeted interviewer `probe_questions` inside `callback_packet_json`.
   - Strict `schemas/gap_artifact.schema.json` representation is always returned under `schema_artifact` on analysis, read, and verification responses.

2. **D2 30-Second Callback Cheat Sheet Builder (`CallbackCheatSheetBuilder`, `build_callback_packet`):**
   - Automatically populates and refreshes `applications.callback_packet_json` across:
     - `POST /api/pipeline/prepare-ai`
     - `POST /api/pipeline/applications/<id>/copilot` & `POST /api/pipeline/jobs/<job_id>/copilot`
     - `POST /api/pipeline/applications/<id>/confirm`
     - `POST /api/pipeline/gaps/<id>/verify` (for unconfirmed, non-demo apps on the same `job_id`)
     - `GET` & `POST /api/pipeline/applications/<id>/callback-packet`
   - Preserves `status == 'confirmed'` immutability (`409 Conflict` on mutation overrides, `200` `immutable: true` on reads) and never alters `test_submitted` demo applications.

---

## Endpoints Ready for Owner B (`B-04`)

- `GET /api/pipeline/gaps` — Lists all persisted `gap_artifacts` rows and `by_job` summaries (with `wording_gaps`, `skill_gaps`, `schema_artifact`).
- `GET /api/pipeline/jobs/<job_id>/gaps` — Returns persisted D5 gap analysis & `schema_artifact` for `<job_id>`.
- `POST /api/pipeline/gaps/analyze` — Runs `GapBridgeAdapter.analyze` (`mode`: `auto` | `llm` | `heuristic`), persists/updates `gap_artifacts` while preserving existing `verified=1` proofs. *(Note: `POST /api/pipeline/gaps` remains `501` to honor `tests/test_contracts.py`.)*
- `POST /api/pipeline/gaps/<gap_id>/verify` — Validates public `proof_url` (SSRF-safe), sets `verified=1` on `true_skill_gap`, refreshes unconfirmed callback packets, and unlocks the skill for future `/api/pipeline/prepare-ai` runs.
- `GET /api/pipeline/applications/<app_id>/callback-packet` — Returns the ready-to-render 30-second Callback Cheat Sheet (`callback_packet`) and `immutable` flag (synthesizes read-only if legacy row lacks full fields).
- `POST /api/pipeline/applications/<app_id>/callback-packet` — Rebuilds/persists `callback_packet_json` (`mode`: `heuristic` | `auto` | `llm`) for non-confirmed, non-demo apps; returns `409` if a caller attempts mutating overrides on `confirmed` or writes to `test_submitted`.

---

## `applications.callback_packet_json` Contract for `B-04` Callback Trigger UI

When `B-04` detects an interview/recruiter reply (`InboxAdapter` classifying `interview` or `recruiter_reply`), render `applications.callback_packet_json` (or fetch `GET /api/pipeline/applications/<app_id>/callback-packet`) with the following JSON shape:

```json
{
  "job_id": 1,
  "job_title": "Backend Engineer",
  "company": "Acme Corp",
  "job_url": "https://boards.greenhouse.io/acme/jobs/123",
  "ats_family": "greenhouse",
  "why_this_role": "2-sentence grounded pitch anchored in candidate evidence and verified gap proofs.",
  "diff_summary": [
    {
      "change_type": "tailor_edit",
      "original": "Master resume excerpt",
      "edited": "Tailored resume excerpt",
      "summary": "Matched job terminology cleanly"
    }
  ],
  "submitted_answers": {
    "why_company_and_role": "...",
    "sensitive_fields_confirmed": true
  },
  "probe_questions": [
    "Targeted interviewer question 1 (tied to verified gap proof if present)",
    "Targeted interviewer question 2 (tied to highlighted/modified resume bullet)",
    "Targeted interviewer question 3 (tied to shared job stack / architecture)"
  ],
  "verified_gap_proofs": [
    {
      "skill_name": "Kubernetes",
      "proof_url": "https://github.com/candidate/k8s-micro-proof",
      "micro_project_brief": "..."
    }
  ],
  "shared_keywords": ["python", "sql"],
  "resume_sha256": "...",
  "answers_sha256": "...",
  "confirmation_reference": "GH-CONF-...",
  "submitted_at": "2026-11-13T...",
  "callback_generation_mode": "deterministic",
  "tailor_changes": [],
  "tailor_summary": {},
  "updated_at": "2026-11-13T..."
}
```

### Privacy & Grounding Guarantees
- Sensitive EEO/work-auth/salary fields (`SENSITIVE_FIELDS`) are excluded from `callback_packet_json.submitted_answers`.
- `confirmed` applications retain immutable `callback_packet_json` and `resume_sha256` / `answers_sha256` hashes for audit verification during recruiter callbacks.
- `test_submitted` demo records stay isolated and never mix into real `confirmed` receipts.
