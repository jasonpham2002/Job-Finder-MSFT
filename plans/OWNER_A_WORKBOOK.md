# Teammate A Workbook — Core Pipeline, AI Tailoring & Apply

**Owner:** Teammate A  
**Exclusive Files:** `app/engine.py`, `app/routes_pipeline.py`, `app/adapters_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py`  
**Shared Rules:** Check `comms/BOARD.md` before starting; post `H-02` in `comms/handoffs/` as soon as `ModelAdapter` is ready so Owner B can reuse it.

---

## Task A-01: `ModelAdapter` (OpenAI/Gemini/Anthropic) + `ResumeFileAdapter` (PDF/DOCX/TXT)
- **Goal:** Support real multi-provider LLM calls and judge-provided PDF/DOCX resumes (Acceptance Test #2).
- **Build:**
  - Implement `UnifiedModelAdapter(ModelAdapter)` in `app/adapters_pipeline.py` reading `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY` from environment variables (never hardcoded) with strict JSON schema output parsing and retry/timeout handling.
  - Implement `LocalResumeFileAdapter(ResumeFileAdapter)` using `pypdf` and `python-docx` (with plain-text fallback) plus `extract_plain_preview(file_bytes, filename)` for ATS linearization checks (`D2`).
  - Expose upload endpoint `POST /api/pipeline/resume/upload` in `app/routes_pipeline.py` and UI upload widget in `web/pipeline.js`.
- **Done when:** A sample PDF/DOCX parses cleanly without saving secrets, `ModelAdapter` returns structured JSON using `prompts/`, and Owner B receives handoff `H-02`.

## Task A-02: `JobDiscoveryAdapter` + D1 Pre-Flight Shield
- **Goal:** Accept arbitrary URLs across 3+ job-site families (`Greenhouse`, `Lever`, `Ashby`, `Workday`, `LinkedIn`, `Indeed`, unseen domains) with honest fallback and D1 risk/ROI analysis.
- **Build:**
  - Add public ATS JSON board fetchers (Greenhouse, Lever, Ashby public APIs) + clean HTML/JSON-LD extraction in `app/engine.py` / `app/adapters_pipeline.py`, keeping SSRF `valid_public_url` checks intact.
  - Implement `preflight_job(job)` (`D1`): detect `ats_family`, check `datePosted`/`validThrough`, flag scam/reference-harvesting/malware-repo indicators, and compute `friction_roi`. Save to `jobs.ats_family` & `jobs.preflight_json`.
  - Add `POST /api/pipeline/jobs/discover` and `POST /api/pipeline/jobs/<id>/preflight` in `app/routes_pipeline.py` + render Pre-Flight badges in `web/pipeline.js`.
- **Done when:** Blocked URLs (like LinkedIn login gates) gracefully fall back to pasted JD without crashing or bypassing controls, and `fictional_jobs` + unseen test URLs show accurate Pre-Flight badges.

## Task A-03: D3 Co-Pilot Packet + Tamper-Evident Receipts
- **Goal:** Enable safe, fast, verifiable real submissions across any portal (including Workday) toward the **10 real applications** rubric goal.
- **Build:**
  - Implement `CoPilotApplicationAdapter(ApplicationAdapter)` generating ordered copy-paste field cards (`copilot_packet`), locking sensitive eligibility questions (`work_auth`, `visa`, `salary`, `veteran`, `disability`, `references`) behind explicit user confirmation.
  - Add `POST /api/pipeline/applications/<id>/copilot` and `POST /api/pipeline/applications/<id>/confirm` computing `resume_sha256` & `answers_sha256`, recording `confirmation_reference`, `submitted_at`, and logging to `audit_events`.
  - Keep `test_submitted` completely separate from `confirmed`.
- **Done when:** Candidate can review, approve, copy-paste into an ATS portal, record confirmation ID/notes, and see verified evidence in `/api/summary` (`real_submitted`).

## Task A-04: D2 Voice-Preserving "Anti-Slop" Tailor + ATS Preview
- **Goal:** Produce truthful, role-tailored resumes without AI clichés or ATS parser corruption.
- **Build:**
  - Upgrade `POST /api/pipeline/prepare-ai` using `ModelAdapter` + `prompts/resume_tailor_prompt.md`: return tailored text, `claim_evidence_map` (`claim → source_snippet`), `unverified_claims`, and `questions_for_candidate`.
  - Add deterministic `lint_ai_slop(text)` in `app/engine.py` flagging cliché words and returning `slop_warnings`.
  - Render side-by-side **Claim Trace**, **Slop Warnings**, and **See What Workday Sees (`ats_preview_text`)** in `web/pipeline.js`, plus optional clean DOCX/PDF export.
- **Done when:** Every edited bullet maps to verified candidate evidence and no unsupported skill appears in the tailored output.

## Task A-05: D5 Gap-to-Proof Bridge + D2 Callback Cheat Sheet Snapshot
- **Goal:** Turn missing skills into honest micro-projects and eliminate post-submit "interview amnesia."
- **Build:**
  - Split gaps into `wording_gap` vs `true_skill_gap`, persist `gap_artifacts` rows (`POST /api/pipeline/gaps/<id>/verify`), and generate 48-hour micro-project briefs.
  - Populate `applications.callback_packet_json` on preparation/submission (`diff_summary`, `submitted_answers`, `why_this_role`, `probe_questions`) and post handoff `H-03` for Owner B's reply tracker.
- **Done when:** Verified micro-projects become reusable candidate evidence, and every prepared/confirmed application has a populated `callback_packet_json`.

## Task A-06 (Optional if Time Permits): Headed Playwright HITL Autofill
- **Goal:** Speed up supported Greenhouse/Lever/Workday non-sensitive fields in a visible browser while keeping the human user in control of login, CAPTCHA, and Submit.
- **Build:** Guarded behind `config.enable_playwright_hitl`; gracefully degrades to `D3` Co-Pilot Packet if Playwright isn't installed on Computer B.

## Task A-07: Unit Tests + Live Submissions
- **Goal:** Add `tests/test_pipeline.py` covering Pre-Flight scam flags, Anti-Slop linter, SHA-256 receipts, and Gap-to-Proof verification; collaborate with Teammate B to complete 10 verified real applications.

---

### Ready-to-Paste Kickoff Prompt for Teammate A's AI Agent
> Read `AGENTS.md`, `plans/TEAM_CHARTER.md`, `plans/DIFFERENTIATORS_SPEC.md`, `plans/OWNER_A_WORKBOOK.md`, and `comms/BOARD.md`. Claim task `A-01` in `comms/BOARD.md`, implement `ModelAdapter` + `ResumeFileAdapter` inside `app/adapters_pipeline.py` and `app/routes_pipeline.py` (do not edit Owner B files or frozen contracts without an ADR), add unit tests in `tests/test_pipeline.py`, run `python3 -m unittest discover -s tests -v` and `python3 scripts/validate_package.py`, then post handoff `H-02` in `comms/handoffs/`.
