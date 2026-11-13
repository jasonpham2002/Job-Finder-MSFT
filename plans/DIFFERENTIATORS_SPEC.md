# Technical Specification — The 5 Differentiators

Every differentiator addresses a real failure mode discovered in community/social research (Hacker News, AIHawk GitHub Issues, Reddit, Blind, Dev.to) while strictly obeying `docs/SECURITY_AND_CONSENT.md`.

---

## D1 — Ghost-Job, Scam & Friction-ROI Pre-Flight Shield *(Owner A)*

**Problem Solved:** Applicants waste hours on stale/evergreen ghost postings, staffing-agency reference-harvesting traps, and malware coding tests, while overlooking high-friction portals (Workday/Ashby) where bot competition drops dramatically.

**Implementation Contract (`JobDiscoveryAdapter.preflight_job` / `app/engine.py`):**
1. **ATS & Canonical Domain Detection:** Classify URL into `greenhouse`, `lever`, `ashby`, `workday`, `linkedin`, `indeed`, `company_site`, or `unknown`. Prefer canonical employer/ATS domains over third-party mirrors.
2. **Liveness Signals:** Inspect JSON-LD `datePosted` and `validThrough`, check for expired/closed strings (`"no longer accepting"`, `"position filled"`), and flag postings older than 30 days or missing dates as `needs_review`.
3. **Scam & Reference-Harvesting Detector:** Scan JD text for red flags:
   - Demanding manager references upfront before interviews
   - Pivoting off-platform to Telegram/WhatsApp/Signal
   - Pre-offer SSN, bank routing, or driver's license requests
   - Untrusted repo/npm take-home instructions (`npm install` from obscure personal repos or custom video software downloads)
4. **Friction-ROI Badge:** Score `high_roi_low_bot_noise` (fresh direct company/Workday/Ashby/Greenhouse URL) vs `saturated_easy_apply` vs `high_risk`.
5. **Storage & UI:** Persist JSON in `jobs.preflight_json` matching `schemas/job.schema.json#properties.preflight`; render clear color-coded pills in `web/pipeline.js`.

---

## D2 — Voice-Preserving "Anti-Slop" Tailor + ATS Preview + Callback Cheat Sheet *(Owner A + Owner B UI trigger)*

**Problem Solved:** Hiring managers reject "bloodless AI prose" (`HN 37761045`), candidates forget AI-rewritten bullets during live calls, and multi-column PDFs scramble horizontally inside Workday parsers.

**Implementation Contract (`ModelAdapter` + `ResumeFileAdapter` + `applications` table):**
1. **Claim-Evidence Map (`claim_evidence_map`):** Every rewritten/reordered bullet must cite an exact source line or snippet from the uploaded candidate resume (`claim` → `source_snippet`). Any unverified claim is blocked and moved to `questions_for_candidate`.
2. **Anti-Slop Linter (`slop_warnings`):** Deterministic regex/dictionary check flagging recognizable LLM clichés (*"spearheaded," "synergistic," "delved," "orchestrated," "testament," "cutting-edge," "dynamic professional"*) and nudging toward concise candidate-voiced verbs.
3. **ATS Plain-Text Linearization Preview (`ats_preview_text`):** Pass the exported/uploaded PDF or DOCX through `ResumeFileAdapter.extract_plain_preview()` and display the raw extracted reading order side-by-side so the user detects mangled columns or dates (`MM/YYYY`) before submitting.
4. **30-Second Callback Cheat Sheet (`callback_packet_json`):** Save an immutable per-application snapshot:
   - `diff_summary` (top changes made vs. master resume)
   - `submitted_answers` (exact custom question answers)
   - `why_this_role` (2-sentence summary)
   - `probe_questions` (3 likely interviewer deep-dive questions tied to highlighted bullets)
   - Triggered automatically in Owner B's Reply Tracker (`web/outreach.js`) whenever a matching recruiter reply arrives.

---

## D3 — Human-Assist Co-Pilot Packet + Optional Headed Playwright HITL + Consent Receipts *(Owner A)*

**Problem Solved:** Mass auto-apply bots trigger LinkedIn bans in 12 hours, break on Workday Shadow DOMs, hallucinate visa/salary answers, and leave no proof of submission (`AIHawk Issue #1158`).

**Implementation Contract (`ApplicationAdapter` + `audit_events`):**
1. **Structured Co-Pilot Packet (`copilot_packet`):** Stage every application field in portal order (`contact_info`, `work_history`, `custom_questions`) with one-click copy buttons in `web/pipeline.js`.
2. **Sensitive Field Hard-Lock:** `work_authorization`, `visa_sponsorship`, `salary_expectation`, `veteran_status`, `disability_status`, and `references` can **never** be LLM-generated—they require explicit candidate input/confirmation.
3. **Optional Headed Playwright HITL (`enable_playwright_hitl`):** Only when explicitly enabled and on supported non-restricted forms (e.g., Greenhouse/Lever), open a visible browser to pre-fill non-sensitive fields and **pause** for human login, CAPTCHA, review, and click-submit. Never bypass protections.
4. **Tamper-Evident Receipt:** Store `resume_sha256`, `answers_sha256`, `approved_at`, `submitted_at`, `confirmation_reference` (ATS ID / email / screenshot note), and log to `audit_events`. Never mark `confirmed` without external confirmation evidence (`manual_required` or `unknown` otherwise).

---

## D4 — Artifact-First Warm Networking + Cooldown & Opt-Out Firewall *(Owner B)*

**Problem Solved:** Cold LinkedIn DMs are saturated with robotic flattery, and automated LinkedIn scraping/messaging risks account suspension.

**Implementation Contract (`ProfessionalContactAdapter` + `OutreachAdapter` + `contacts` table):**
1. **Legitimate Public Artifact Discovery:** Search company `/team`, `/about`, `/engineering` blogs, public GitHub org contributors, conference speaker lists, or user-pasted LinkedIn profile URLs.
2. **Verified Artifact Hook (`artifact_hook`):** Require a verifiable source URL + snippet (`type`: `blog_post|github_repo|talk|team_bio|user_provided`, `title`, `url`, `snippet`) before drafting outreach. Never guess unlisted email addresses.
3. **Anti-Flattery 3-Sentence Draft:** Reference the specific artifact + one verified resume overlap + polite optional question (never fake familiarity or guaranteed referral asks).
4. **Cooldown & Opt-Out Firewall:** Check `contacts.opted_out` and company-level cooldown (`company_outreach_cooldown_days`, default `14`, plus `max_contacts_per_company`) in SQLite before permitting `OutreachAdapter.send(...)`.

---

## D5 — Gap-to-Proof Bridge *(Owner A)*

**Problem Solved:** Keyword filters screen out strong candidates missing 1–2 skills, while hiring managers favor demonstrable proof-of-work over padded resumes.

**Implementation Contract (`gap_artifacts` table + `schemas/gap_artifact.schema.json`):**
1. Classify `unmatched_job_keywords` into:
   - `wording_gap`: candidate already has the experience phrased differently → eligible for truthful resume rewording.
   - `true_skill_gap`: candidate lacks verified evidence → **strictly blocked from resume**.
2. For top `true_skill_gap` items (or peer-inspired skills), generate a concise **48-hour micro-project brief** (`micro_project_brief`).
3. Allow the candidate to log a completed proof link (`proof_url`) and mark `verified = true`, legitimately unlocking that skill for future applications.
