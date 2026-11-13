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

Distinct real applications with confirmations: ____ / 10
Distinct approved outreach messages actually sent: ____ / 10
Human replies confirmed: ____
Referral opportunities confirmed: ____
Interview invitations confirmed: ____
Demo/test submissions (not real): ____

## Portability

Verified Computer B or clean-environment setup: yes / no
Skill ZIP files included: yes / no
Ran with a second AI provider: yes / no
Items needing re-authentication: __________
Known limitations/bugs: __________

## Current Scaffold Baseline (Honesty Status)

- **Real / Live today:** Local HTTP dashboard (`127.0.0.1:8765`), SSRF-checked public HTML + `schema.org/JobPosting` parser with manual paste fallback, SQLite persistence with idempotent migrations, typed adapter & schema contracts (`D1`–`D5`), modular Owner A/B route & UI seams, and portable `SKILL.md` packaging.
- **Test / Stubbed today (update above before final judging):** `ModelAdapter`, PDF/DOCX `ResumeFileAdapter`, `JobDiscoveryAdapter`, `ApplicationAdapter` real submissions, `ProfessionalContactAdapter`, and `InboxAdapter` live sync remain offline/stubbed.
- **B-01 email delivery:** Gmail supports authorized delivery through the local API. Tests mock Google, and this implementation run recorded zero live sends. Outlook and LinkedIn use manual copy/paste. A user-reported `manual_sent` is tracked separately from Gmail sends with a provider message ID.

### B-01 local setup and API

1. Enable Gmail API in your Google Cloud project and create a **Desktop app** OAuth client. Install `google-auth-oauthlib` in the Python environment used to authorize Gmail.
2. Set `GMAIL_OAUTH_CLIENT_ID` and `GMAIL_OAUTH_CLIENT_SECRET` in the process environment. Run `python -m app.adapters_outreach authorize-gmail` and grant the Gmail send scope in the browser. The refresh token is stored in `~/.jobfinder/gmail-outreach.json` outside the project. Start the server with the same environment. Each user should authorize their own account.
3. POST to `/api/networking/outreach/drafts` with `job_id`, `name`, `role`, `source_url`, `recipient`, `channel` (`email` or `linkedin`), `subject`, `body`, and `user_authorized_recipient: true`. Review the returned job URL, destination and final message. Keep the returned review_token and include it in each subsequent POST for that draft. This route stages a delivery draft from user-reviewed content, which can be copied from the existing draft preview and edited before staging.
4. POST to `/api/networking/outreach/<id>/approve` with `explicit_user_approval: true` and `reviewed_message` containing exactly `job_url`, `channel`, `recipient`, `subject`, and `body` from the staged draft. Optionally specify `provider` as `gmail`, `outlook`, or `manual`. Gmail is the email default and LinkedIn uses manual delivery.
5. POST to `/api/networking/outreach/<id>/send` with `explicit_user_approval: true`. For `manual_required`, copy the returned message and send it yourself. Then POST to `/api/networking/outreach/<id>/manual-sent` with `explicit_user_approval: true` and `confirmed_manually_sent: true`. If a Gmail attempt is `unknown` or remains `sending` after an interruption, check Gmail Sent before taking further action.

## Privacy and validation

- [ ] No secrets or personal user data inside ZIP
- [ ] Approval required for real submissions/outreach
- [ ] No site protection bypass or prohibited scraping
- [ ] No fictional test data used in live applications
- [ ] All claimed success statuses have external evidence
- [ ] Instructions let the judge run the solution without our personal accounts
