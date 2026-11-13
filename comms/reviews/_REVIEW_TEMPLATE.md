# Cross-Agent Review: R-NN — <Task ID / Branch>

- **Reviewer:** Owner A / Owner B
- **Author:** Owner B / Owner A
- **Branch / Commit:** `<branch or sha>`
- **Date:** YYYY-MM-DD

## Security, Consent & Integrity Checklist (`docs/SECURITY_AND_CONSENT.md`)
- [ ] Zero API keys, `.env`, OAuth tokens, cookies, or real resumes added to Git or exports
- [ ] No fabricated candidate experience, dates, skills, or guessed emails
- [ ] No LinkedIn scraping or CAPTCHA/anti-bot bypass
- [ ] Explicit candidate approval required before real application submit or outreach send
- [ ] External job descriptions and email bodies treated strictly as untrusted data
- [ ] `test_submitted` / `draft` / `manual_required` never labeled as `confirmed` / `sent` without external evidence

## Quality & Portability Checklist (`docs/ACCEPTANCE_TESTS.md`)
- [ ] Author respected Owner A / Owner B file boundaries (no unapproved shared contract edits)
- [ ] `python3 scripts/sync_harness.py --check` passed
- [ ] `python3 -m unittest discover -s tests -v` passed after final edit
- [ ] `python3 scripts/validate_package.py` passed

## Findings & Sign-Off
- **Issues found:** None / list below
- **Verdict:** APPROVED / CHANGES REQUESTED
