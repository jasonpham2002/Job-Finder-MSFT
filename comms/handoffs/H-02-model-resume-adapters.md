# Handoff Ticket: H-02 — `UnifiedModelAdapter` & `LocalResumeFileAdapter` Ready (`A-01`)

- **From:** Owner A
- **To:** Owner B (unblocks `B-02` Reply Classifier & `B-03` Outreach Drafting)
- **Related Task ID:** `A-01`
- **Date:** 2026-11-13 11:42

## Contract / Interface Exposed
- **Module(s) & symbol(s):** `app/adapters_pipeline.py`
  - `UnifiedModelAdapter(ModelAdapter)` & `get_model_adapter(provider=None, model=None, ...)`
    - `.generate(system_prompt: str, user_prompt: str, output_schema: Optional[dict[str, Any]] = None) -> dict[str, Any]`
    - `.generate_from_prompt(prompt_name: str, user_data: str, output_schema: Optional[dict[str, Any]] = None, include_system_guardrails: bool = True) -> dict[str, Any]`
    - `.inspect_capabilities() -> dict[str, Any]` (safe readiness metadata; zero secrets)
  - `load_prompt(name: str) -> str`, `load_local_env(...)`, `load_pipeline_config(...)`
  - Exceptions: `ModelAdapterError`, `ModelNotConfiguredError` (fall back cleanly to deterministic logic when caught!), `ModelRequestError`, `ModelOutputError`
  - `LocalResumeFileAdapter(ResumeFileAdapter)` (`.extract()`, `.extract_plain_preview()`, `.extract_bundle()`, `ResumeFileError`, `analyze_ats_preview()`)
- **Endpoint(s) & DB table(s) populated:**
  - `GET /api/pipeline/status` (returns readiness for `model_adapter` and `resume_adapter`; never exposes secrets)
  - `POST /api/pipeline/resume/upload` (accepts JSON `{filename, content_base64 | text, save_to_profile}`, updates `profile` row `id=1`, logs sanitized SHA-256 metadata to `audit_events`)
- **Schema reference:** Follows `ModelAdapter` and `ResumeFileAdapter` contracts in `app/adapters.py`; no frozen contracts or Owner B files modified.

## Summary of Changes
- Implemented multi-provider `UnifiedModelAdapter` supporting OpenAI (`OPENAI_API_KEY`, default `gpt-4o-mini`), Google Gemini Interactions API (`GEMINI_API_KEY`, default `gemini-3.8-flash`, `store=False`), and Anthropic (`ANTHROPIC_API_KEY`, default `claude-haiku-5-5`) over Python stdlib `urllib.request` with strict JSON schema validation, retry/backoff, untrusted-data isolation, and secret redaction.
- Implemented in-memory `LocalResumeFileAdapter` supporting `.pdf` (`pypdf` primary + stdlib `FlateDecode` fallback), `.docx` (`python-docx` primary + stdlib ZIP/XML fallback), and `.txt`/`.md`, plus `D2` ATS plain-text linearization preview (`extract_plain_preview`).
- Added `POST /api/pipeline/resume/upload` in `app/routes_pipeline.py`, upload + ATS preview widget in `web/pipeline.js`, and 16 offline-deterministic unit tests in `tests/test_pipeline.py`.

## Verification Executed
- `python3 -m unittest discover -s tests -v`: 29/29 tests passing (including `test_pipeline.py`, `test_api.py`, `test_contracts.py`, `test_engine.py`, `test_portability.py`).
- `python3 scripts/sync_harness.py --check`: all 6 skills in `.agents/skills/` match `skills/`.
- Clean export verification via `scripts/export_handoff.py` + `scripts/validate_package.py` in an isolated temp extraction directory passed (note: running `validate_package.py` directly in a dev workspace containing `.env` or `local_demo.sqlite3` fails by design on the pre-sharing clean check).

## Action Needed by Receiving Teammate
- **Owner B (`B-02` & `B-03`):** Call `get_model_adapter().generate_from_prompt('reply_classification_prompt', email_text, output_schema=...)` or `get_model_adapter().generate(...)`, catching `ModelNotConfiguredError` to fall back gracefully to deterministic offline logic when no API key is configured.
