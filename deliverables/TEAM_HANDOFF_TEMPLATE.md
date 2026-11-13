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
- **Test / Stubbed today (must be implemented & updated above before final judging):** `ModelAdapter`, PDF/DOCX `ResumeFileAdapter`, `JobDiscoveryAdapter`, `ApplicationAdapter` real submissions, `ProfessionalContactAdapter`, `OutreachAdapter` real email sending, and `InboxAdapter` live sync all remain offline/stubbed (`501`/`NotImplementedError`), and `real_submitted` / `real_outreach_sent` remain `0` until teammates wire live credentials and record real confirmations.

## Privacy and validation

- [ ] No secrets or personal user data inside ZIP
- [ ] Approval required for real submissions/outreach
- [ ] No site protection bypass or prohibited scraping
- [ ] No fictional test data used in live applications
- [ ] All claimed success statuses have external evidence
- [ ] Instructions let the judge run the solution without our personal accounts
