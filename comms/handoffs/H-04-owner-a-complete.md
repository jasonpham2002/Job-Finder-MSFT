# Handoff H-04 — Owner A Complete (`A-01` through `A-07`, All D1–D5 Pipeline Capabilities Ready)

**From:** Owner A (`A-06`, `A-07`)  
**To:** Owner B (`B-01`..`B-07` Networking, Inbox, `TEAM_HANDOFF_TEMPLATE.md`, Computer B QA)  
**Status:** Ready  
**Branch:** `feat/a-06-07-hitl-submissions`

---

## Summary of Completed Owner A Capabilities (`A-01`..`A-07`)

Owner A's full pipeline is now complete and isolated inside Owner A's exclusive file zone (`app/engine.py`, `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py`):

1. **`A-01` Model & File Foundation (`H-02`):** `UnifiedModelAdapter` (`openai` / `gemini` / `anthropic`, `<UNTRUSTED_DATA>` isolation, retries, JSON schema validation, secret redaction) and `LocalResumeFileAdapter` (`.pdf`, `.docx`, `.txt`, `.md`, ATS plain-text preview).
2. **`A-02` Job Discovery & D1 Pre-Flight Shield:** Public ATS board feeds (`greenhouse`, `lever`, `ashby`), SSRF-checked URL importer with manual fallback, `datePosted`/`validThrough`/scam/ROI `preflight_json` badges.
3. **`A-03` D3 Co-Pilot Packet & SHA-256 Receipts:** Ordered ATS portal sections, locked `SENSITIVE_FIELDS` (`work_authorization`, `visa_sponsorship`, `salary_expectation`, `veteran_status`, `disability_status`, `references`), explicit-approval gate, duplicate confirmed-submission guard, `test_submitted` isolation, `resume_sha256` + `answers_sha256`.
4. **`A-04` D2 Voice-Preserving Anti-Slop Tailor & OOXML Preview:** Claim-to-evidence verification, `lint_ai_slop`, Workday plain-text preview, ATS-clean `.docx` export.
5. **`A-05` D5 Gap-to-Proof Bridge & D2 Callback Cheat Sheet (`H-03`):** `GapBridgeAdapter` (`wording_gap` vs `true_skill_gap` with 48h project briefs and public SSRF-safe proof URL verification) + `CallbackCheatSheetBuilder` populating `applications.callback_packet_json`.
6. **`A-06` Optional Headed Playwright HITL Autofill:** `PlaywrightHITLHelper` & `CoPilotApplicationAdapter.launch_hitl_autofill` — lazy zero-hard-dependency import (`enable_playwright_hitl` config gate), pre-fills ONLY non-sensitive fields on verified public URLs, never clicks Submit, never touches `SENSITIVE_FIELDS`, and degrades gracefully to D3 Co-Pilot Packet (`mode: "copilot_fallback"`) when disabled or unavailable on Computer B.
7. **`A-07` 10-Job Pipeline Batch & Live Submission Readiness Scorecard:** `POST /api/pipeline/queue-batch` and `GET /api/pipeline/readiness` stage up to 10 distinct jobs with full D1–D5 artifacts while keeping honest separation between `draft`, `test_submitted` (demo only), and externally verified `confirmed` real applications.

---

## Endpoints Ready for Owner B & Judge Verification

- `GET /api/pipeline/status` — Reports completed `A-01..A-07`, active LLM provider, Serper status, D3/D5 readiness, and `playwright_available` / `playwright_hitl_enabled`.
- `POST /api/pipeline/applications/<id>/hitl-autofill` — Requires `explicit_user_approval: true`; returns `mode: "playwright_hitl"` or graceful `"copilot_fallback"` with selector plan & D3 Co-Pilot packet (`403` without approval, `409` on `confirmed` / `test_submitted`).
- `POST /api/pipeline/queue-batch` — Runs D1 Pre-Flight, D5 Gap Analysis, D2 Anti-Slop Tailor, D3 Co-Pilot staging, and D2 Callback Cheat Sheet across up to `limit` (default `10`) jobs without modifying `confirmed` or `test_submitted` rows.
- `GET /api/pipeline/readiness` — Live scorecard tracking progress toward `10` prepared roles (`ten_job_pipeline_ready`) and `10` real confirmed submissions (`ten_real_submissions_reached`) with per-application artifact checks.

---

## Notes for Owner B (`B-06` / `deliverables/TEAM_HANDOFF_TEMPLATE.md`)

- `Playwright` is **optional** (`config.example.json` keeps `"enable_playwright_hitl": false` and `"enable_real_apply": false`). A clean judge machine runs cleanly without Playwright installed.
- `POST /api/pipeline/gaps` still returns `501` to preserve `tests/test_contracts.py` contract assertions; all live D5 gap operations use `/api/pipeline/gaps/analyze`, `/api/pipeline/gaps/<id>/verify`, `/api/pipeline/gaps`, and `/api/pipeline/jobs/<id>/gaps`.
- All Owner A unit tests pass cleanly in offline deterministic mode (`tests/test_pipeline.py` mocks DNS `socket.getaddrinfo` only inside gap/HITL SSRF test cases so clean sandboxes without internet still test full IP validation logic).
