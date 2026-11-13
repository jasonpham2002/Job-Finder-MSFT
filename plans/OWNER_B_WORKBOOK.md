# Teammate B Workbook — Artifact Contacts, Outreach, Inbox & Portability

**Owner:** Teammate B  
**Exclusive Files:** `app/routes_outreach.py`, `app/adapters_outreach.py`, `web/outreach.js`, `skills/*/SKILL.md`, `prompts/*.md`, `deliverables/TEAM_HANDOFF_TEMPLATE.md`, `tests/test_outreach.py`  
**Shared Rules:** Check `comms/BOARD.md` before starting; consume Owner A's `ModelAdapter` after `H-02` and `callback_packet_json` after `H-03`.

---

## Task B-01: Gmail OAuth Primary + Outlook Contract `OutreachAdapter`
- **Goal:** Enable authorized, audited email sending toward the **10 approved outreach messages** rubric target, with manual copy-paste LinkedIn fallback.
- **Build:**
  - Implement `GmailOutreachAdapter(OutreachAdapter)` in `app/adapters_outreach.py` using local desktop OAuth (`GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`, token stored locally outside Git/exports) + clean `OutlookOutreachAdapter` contract (`OUTLOOK_CLIENT_ID`).
  - Expose `POST /api/networking/outreach/<id>/approve` and `POST /api/networking/outreach/<id>/send` in `app/routes_outreach.py`, refusing sends without `explicit_user_approval=True` and recording `provider_message_id` + `sent_at` + `audit_events`.
  - Never mark a LinkedIn draft as `sent` automatically—provide `manual_sent` confirmation toggle with timestamp.
- **Done when:** Approved test/real email returns a real Gmail message ID, unauthorized sends raise `PermissionError`, and no OAuth token sits in tracked folders.

## Task B-02: `InboxAdapter` + Thread Reply Classifier
- **Goal:** Monitor authorized inbox threads and separate automated receipts from real human replies, referrals, rejections, and interview invites (Acceptance Test #10).
- **Build:**
  - Implement `GmailInboxAdapter(InboxAdapter)` syncing recent recruiting/outreach threads, deduplicating by `provider_message_id`, and classifying via `ModelAdapter` (or deterministic fallback) using `prompts/reply_classification_prompt.md` + treating email bodies strictly as untrusted data.
  - Support synthetic `sample_data/fictional_inbox.json` injection endpoint (`POST /api/inbox/simulate`) clearly labeled `TEST ONLY` so judges can test Acceptance Test #10 offline!
  - Expose `POST /api/inbox/sync` and `GET /api/inbox/replies` in `app/routes_outreach.py` + render Inbox Tracker in `web/outreach.js`.
- **Done when:** `fictional_inbox.json` classifies `human_positive_reply`, `automated_receipt`, and `rejection` accurately without counting auto-receipts as human replies.

## Task B-03: D4 Artifact-First Public Contact Research
- **Goal:** Discover up to 3 real, relevant contacts (recruiter, hiring manager, role peer) per job without prohibited LinkedIn scraping or email guessing.
- **Build:**
  - Implement `PublicArtifactContactAdapter(ProfessionalContactAdapter)` querying legitimate public sources (company `/team`, `/about`, `/blog` pages, public GitHub org contributors API, or user-pasted LinkedIn/profile URLs) and extracting `artifact_hook` (`type`, `title`, `url`, `snippet`).
  - Never guess email patterns; only save `public_email` when verifiably published (`verified_public` vs `user_provided` vs `unverified`).
  - Upgrade outreach drafting to 3 crisp, artifact-anchored, anti-flattery sentences using `prompts/outreach_prompt.md` + `ModelAdapter`.
- **Done when:** Contact cards display verified source URL + artifact hook, and `none verified` produces helpful manual search queries instead of invented people.

## Task B-04: Cooldown/Opt-Out Firewall + Callback Cheat Sheet Trigger UI
- **Goal:** Prevent spam/duplicate outreach and surface Owner A's 30-second Callback Cheat Sheet whenever a human reply arrives.
- **Build:**
  - Add `POST /api/networking/contacts/<id>/opt-out` and enforce company-level cooldown (`company_outreach_cooldown_days`) + `opted_out` block before drafting/sending.
  - In `web/outreach.js`, match incoming `replies` back to `applications.callback_packet_json` and render a **"View 30s Callback Cheat Sheet"** drawer showing what resume diff, answers, and probe questions correspond to that company.
- **Done when:** Opted-out contacts or cooldown-blocked companies cannot be messaged, and clicking a human reply shows the exact submitted snapshot.

## Task B-05: Upgrade Portable `skills/*/SKILL.md` & `prompts/*.md`
- **Goal:** Ensure every new capability (D1–D5) is packaged in the portable Agent Skills & prompts (Acceptance Test #11 & +15 multi-provider bonus).
- **Build:**
  - Update `skills/{job-finder,resume-optimizer,company-research,application-preparer,networking-outreach,response-tracker}/SKILL.md` and `prompts/*.md` to include D1–D5 workflows and guardrails.
  - Run `python3 scripts/sync_harness.py` to sync `.agents/skills/` and `python3 scripts/export_skills.py` to rebuild skill ZIPs.
- **Done when:** `sync_harness.py --check` passes and skill ZIPs run cleanly in a second AI harness (e.g., Codex / Claude / Antigravity).

## Task B-06: Clean-Environment Portability Test, Cross-Review & Handoff
- **Goal:** Guarantee a judge on Computer B can extract the ZIP, set their own `.env`, upload a new PDF/DOCX, paste an unseen URL, and run everything cleanly.
- **Build:**
  - Complete `deliverables/TEAM_HANDOFF_TEMPLATE.md` honestly documenting real vs. manual vs. test features and exact submission counts.
  - Run `.agent/workflows/04-cross-review.md` and `.agent/workflows/05-release-handoff.md`; test extracting `exports/jobfinder-complete-portable-handoff.zip` into a clean temp directory with zero `.env`/`.sqlite3`/tokens and run smoke tests.

## Task B-07: Unit Tests + Live Outreach
- **Goal:** Add `tests/test_outreach.py` covering opt-out blocking, cooldown enforcement, reply deduplication, auto-receipt vs. human reply distinction, and artifact validation; collaborate with Teammate A to send 10 approved unique outreach messages.

---

### Ready-to-Paste Kickoff Prompt for Teammate B's AI Agent
> Read `AGENTS.md`, `plans/TEAM_CHARTER.md`, `plans/DIFFERENTIATORS_SPEC.md`, `plans/OWNER_B_WORKBOOK.md`, and `comms/BOARD.md`. Claim task `B-01` in `comms/BOARD.md`, implement Gmail OAuth + manual fallback `OutreachAdapter` inside `app/adapters_outreach.py` and `app/routes_outreach.py` (do not edit Owner A files or frozen contracts without an ADR), add unit tests in `tests/test_outreach.py`, and run `python3 -m unittest discover -s tests -v` and `python3 scripts/validate_package.py`.
