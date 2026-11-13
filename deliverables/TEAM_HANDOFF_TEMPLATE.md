# Team Handoff — Fill This Out Before You Submit

Team name: JobFinder MSFT (Owner A + Owner B)
Repository / project version: JobFinder_Hackathon_4 v1.0 (Tasks A-01..A-07 & B-01..B-07 integrated)
Primary AI provider: Google Gemini (`gemini-3.8-flash` via Interactions API)
Other supported AI providers: OpenAI (`gpt-4o-mini` / Responses & Chat Completions), Anthropic (`claude-3-5-sonnet-latest` / Messages tool-forced JSON), plus deterministic offline fallback

## Setup

Supported OS: macOS, Linux, Windows
Required runtime versions: Python 3.11+ (zero-dependency standard-library runtime; Node.js optional for JS syntax check)
Install command: `python3 -m pip install pypdf google-auth-oauthlib playwright` (all optional; core server, DOCX/PDF/TXT parser, and offline demo run with Python standard library alone)
Start command: `python3 -m app.server` (opens `http://127.0.0.1:8765`)
Required environment variables (NAMES ONLY, NO SECRETS): `JOBFINDER_LLM_PROVIDER`, `JOBFINDER_LLM_MODEL`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SEARCH_API_KEY`, `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`, `OUTLOOK_CLIENT_ID`, `OUTLOOK_TENANT_ID`, `JOBFINDER_PORT`, `JOBFINDER_LLM_OUTREACH`
Required account permissions/plan/API billing: Free or paid API key for chosen LLM provider (`GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), optional Serper API key (`SEARCH_API_KEY`), and Google Cloud Desktop OAuth client for Gmail send (`gmail.send`) and read-only inbox sync (`gmail.readonly`)

## Integrations (real/test/manual)

Job sources supported: Public Greenhouse, Lever, and Ashby board JSON APIs, optional Serper web search (`SEARCH_API_KEY`), arbitrary public company career URLs (`schema.org/JobPosting` + HTML), and manual JD paste fallback for login/anti-bot-gated sites (LinkedIn/Indeed/Workday)
Job-page extraction techniques: SSRF-validated public HTTP fetcher + ATS API adapters (Greenhouse/Lever/Ashby) + `schema.org/JobPosting` JSON-LD + HTML text extractor + D1 Pre-Flight Shield (ATS family, liveness, scam/reference-harvesting detector, friction-ROI badge)
PDF/DOCX parser: `LocalResumeFileAdapter` supporting `.docx` (`zipfile` + `word/document.xml`), `.pdf` (`pypdf` when installed + stdlib zlib Flate stream fallback), and `.txt`, with zip-bomb/size limits and D2 ATS plain-text linearization preview
Application destination(s) and authorization model: D3 Human-Assist Co-Pilot Packet (portal-ordered fields + hard-locked sensitive fields + SHA-256 tamper-evident receipts) + A-06 Optional Headed Playwright HITL Autofill (`enable_playwright_hitl` + `explicit_user_approval=True`; fills non-sensitive fields only and pauses for human review & submit)
Professional contact research source(s): D4 `PublicArtifactContactAdapter` extracting `schema.org/Person` JSON-LD, public HTML team bio cards, and blog author metadata from employer-published URLs (plus user-verified excerpt entry and manual search query fallback)
Email sending provider: `GmailOutreachAdapter` via Desktop OAuth (`~/.jobfinder/gmail-outreach.json`) with `explicit_user_approval=True`, `review_token`, and `message_sha256` verification; `OutlookOutreachAdapter` and `ManualOutreachAdapter` manual fallback
LinkedIn messaging approach (manual/authorized): Strictly manual copy-paste after explicit user approval, with user-reported `manual_sent` confirmation timestamp (zero automated LinkedIn scraping or sending)
Response monitoring provider: `GmailInboxAdapter` syncing messages labeled `JobFinder` (`gmail.readonly` via `~/.jobfinder/gmail-inbox.json`), deduplicating by `provider_message_id`, classifying via `classify_reply`, and triggering Owner A's D2 30-second Callback Cheat Sheet drawer; offline `POST /api/inbox/simulate` (`TEST ONLY`) included

## Evidence

Distinct real applications with confirmations: 0 / 10
Distinct approved recruiting outreach messages actually sent: 0 / 10
Human replies confirmed: 0
Referral opportunities confirmed: 0
Interview invitations confirmed: 0
Demo evidence: one approved Gmail integration email to a user-controlled inbox. Automated smoke-test submissions use a disposable database.

## Portability

Verified clean-environment setup: local extraction, package validation and 67 automated tests passed, including PDF/DOCX fixtures, D1-D5 pipeline tests, A-06 HITL + A-07 readiness scorecard, and B-01..B-07 outreach/inbox tests. Computer B remains pending.
Skill ZIP files included: yes, six individual archives and one combined archive.
Second AI harness or provider: Antigravity (`skills/`) + OpenAI Codex (`.agents/skills/` synchronized via `scripts/sync_harness.py`) + Claude (`CLAUDE.md`).
Items needing re-authentication: Gmail send and Gmail inbox read scopes use separate desktop OAuth credentials (`~/.jobfinder/gmail-outreach.json` and `~/.jobfinder/gmail-inbox.json`).
Known limitations: Live applications (`0/10`) and live recruiting outreach (`0/10`) require human candidate execution and external confirmation IDs. Live Gmail inbox sync requires separate `authorize-gmail-inbox` OAuth consent.

## Current Scaffold Baseline (Honesty Status)

- **Real / Live today:** Local HTTP dashboard (`127.0.0.1:8765`), `UnifiedModelAdapter` (Gemini/OpenAI/Anthropic), `LocalResumeFileAdapter` (PDF/DOCX/TXT + ATS preview), `LiveJobDiscoveryAdapter` (Greenhouse/Lever/Ashby + Serper + D1 Pre-Flight Shield), `VoicePreservingTailorAdapter` (D2 claim-evidence map + anti-slop linter), `GapBridgeAdapter` (D5 wording vs. true skill gaps + proof verification), `CoPilotApplicationAdapter` + `PlaywrightHITLHelper` (D3 Co-Pilot packets, SHA-256 receipts, A-06 optional headed autofill, A-07 10-job batch & readiness scorecard), `PublicArtifactContactAdapter` (D4 JSON-LD + HTML bio/blog extractor), `GmailOutreachAdapter` (B-01 OAuth send + cooldown/opt-out firewall), and `GmailInboxAdapter` (B-02 reply sync/classification + B-04 D2 Callback Cheat Sheet drawer).
- **Requires user credentials / human action for live counts:** Live LLM calls require an API key in `.env`; live Gmail send/sync requires running desktop OAuth; real application (`confirmed`) and outreach (`sent`) scoreboard counts strictly require human review, approval, and external confirmation IDs.
- **B-01 email delivery:** Gmail supports authorized delivery through the local API. Automated tests mock Google. On 2026-11-13, desktop OAuth and one approved Gmail test send through the adapter returned a real message ID. The recipient was a user-controlled inbox, so this test is excluded from the outreach scoreboard. Outlook and LinkedIn use manual copy/paste. A user-reported `manual_sent` is tracked separately from Gmail sends with a provider message ID.

### B-01 local setup and API

1. Enable Gmail API in your Google Cloud project and create a **Desktop app** OAuth client. Install `google-auth-oauthlib` in the Python environment used to authorize Gmail.
2. Set `GMAIL_OAUTH_CLIENT_ID` and `GMAIL_OAUTH_CLIENT_SECRET` in the process environment. Run `python -m app.adapters_outreach authorize-gmail` and grant the Gmail send scope in the browser. The refresh token is stored in `~/.jobfinder/gmail-outreach.json` outside the project. Start the server with the same environment. Each user should authorize their own account.
3. POST to `/api/networking/outreach/drafts` with `job_id`, `name`, `role`, `source_url`, `recipient`, `channel` (`email` or `linkedin`), `subject`, `body`, and `user_authorized_recipient: true`. Review the returned job URL, destination and final message. Keep the returned review_token and include it in each subsequent POST for that draft. This route stages a delivery draft from user-reviewed content, which can be copied from the existing draft preview and edited before staging.
4. POST to `/api/networking/outreach/<id>/approve` with `explicit_user_approval: true` and `reviewed_message` containing exactly `job_url`, `channel`, `recipient`, `subject`, and `body` from the staged draft. Optionally specify `provider` as `gmail`, `outlook`, or `manual`. Gmail is the email default and LinkedIn uses manual delivery.
5. POST to `/api/networking/outreach/<id>/send` with `explicit_user_approval: true`. For `manual_required`, copy the returned message and send it yourself. Then POST to `/api/networking/outreach/<id>/manual-sent` with `explicit_user_approval: true` and `confirmed_manually_sent: true`. If a Gmail attempt is `unknown` or remains `sending` after an interruption, check Gmail Sent before taking further action.

### B-02 Inbox Tracker

Run `python -m app.adapters_outreach authorize-gmail-inbox` with the same OAuth client environment as B-01 and grant Gmail read-only access. This stores a separate token outside the repo. In Gmail, create the `JobFinder` label and apply it to the recruiting or outreach replies you want to sync. Open **Inbox Tracker** in the dashboard and click **Sync JobFinder-labeled Gmail**. Each sync checks up to 100 incoming messages in the last 30 days and stores local previews with suggested classifications. The offline **Test inbox classification** button uses a synthetic fixture and leaves the saved Gmail replies untouched. Live inbox access has not been verified.

### B-03 and B-04 contact and callback workflows

In **Public contact research**, enter an imported real job ID and a public employer team or bio URL. The adapter extracts structured biographies with a matching employer and a published excerpt, and returns manual search queries when it cannot verify a contact. The draft preview uses the artifact URL. With JOBFINDER_LLM_OUTREACH=1, the integrated A-01 model adapter can draft outreach. The live Gemini draft route passed using synthetic data.

Use **Mark opted out** on a contact card to block future drafts and sends. The company cooldown defaults to 14 days and can be set in local `config.json` with `company_outreach_cooldown_days`. In Inbox Tracker, link a likely human reply to a confirmed application. The drawer displays the snapshot stored with that application when one exists.

## Privacy and validation

- [ ] No secrets or personal user data inside ZIP
- [ ] Approval required for real submissions/outreach
- [ ] No site protection bypass or prohibited scraping
- [ ] No fictional test data used in live applications
- [ ] All claimed success statuses have external evidence
- [ ] Instructions let the judge run the solution without our personal accounts
