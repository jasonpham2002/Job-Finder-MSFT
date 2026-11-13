# Team Handoff — Fill This Out Before You Submit

Team name: __________
Repository / project version: __________
Primary AI provider: __________
Other supported AI providers: __________

## Setup

Supported OS: __________
Required runtime versions: __________
Install command: __________
Start command: __________
Required environment variables (NAMES ONLY, NO SECRETS): __________
Required account permissions/plan/API billing: __________

## Integrations (real/test/manual)

Job sources supported: __________
Job-page extraction techniques: __________
PDF/DOCX parser: __________
Application destination(s) and authorization model: __________
Professional contact research source(s): __________
Email sending provider: __________
LinkedIn messaging approach (manual/authorized): __________
Response monitoring provider: __________

## Evidence

Distinct real applications with confirmations: 0 / 10
Distinct approved recruiting outreach messages actually sent: 0 / 10
Human replies confirmed: 0
Referral opportunities confirmed: 0
Interview invitations confirmed: 0
Demo evidence: one approved Gmail integration email to a user-controlled inbox. Automated smoke-test submissions use a disposable database.

## Portability

Verified clean-environment setup: local extraction, package validation and 42 automated tests passed, including PDF/DOCX fixtures. Computer B remains pending.
Skill ZIP files included: yes, six individual archives and one combined archive.
Second AI harness or provider: pending.
Items needing re-authentication: Gmail send and Gmail inbox read scopes use separate desktop OAuth credentials.
Known limitations: PDF/DOCX fixture coverage passed with the integrated A-01 adapter. Real application confirmation depends on Owner A. Live Gmail inbox sync still needs read-only OAuth verification.

## Current Scaffold Baseline (Honesty Status)

- **Real / Live today:** Local HTTP dashboard (`127.0.0.1:8765`), SSRF-checked public HTML + `schema.org/JobPosting` parser with manual paste fallback, SQLite persistence with idempotent migrations, typed adapter & schema contracts (`D1`–`D5`), modular Owner A/B route & UI seams, and portable `SKILL.md` packaging.
- **Test / Stubbed today (update above before final judging):** `ModelAdapter`, PDF/DOCX `ResumeFileAdapter`, `JobDiscoveryAdapter`, `ApplicationAdapter` real submissions, and `ProfessionalContactAdapter` remain offline/stubbed.
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
