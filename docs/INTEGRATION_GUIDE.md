# Integration Guide — Universal Job URLs and Outreach

## A. Job URL adapter strategy

**Normalize to one `Job` object** (see `schemas/job.schema.json`) regardless of site. Build a prioritized chain:

1. Approved partner API / ATS feed, if available.
2. Public structured HTML (`application/ld+json` `JobPosting`), with source URLs and verification timestamps.
3. Public visible HTML extraction if allowed, with review of noisy content.
4. User-authorized browser interaction where permitted and required.
5. Paste job description or upload posting as text when access is blocked or disallowed.

Suggested source families to *accept as URLs*: employer career sites, Indeed, LinkedIn, Workday, Greenhouse, Lever, SmartRecruiters and ZipRecruiter. **URL acceptance is not the same as automated scraping or applying.**

The starter includes generic public structured/HTML extraction with DNS/IP safety checks; it intentionally does **not** log into LinkedIn or bypass protections. Some ATS application form APIs are private or require employer credentials. Do not present employer-only APIs as universal public apply services.

## B. Real application adapters

Make separate adapters behind a common `submit_application` contract. Verify each site's terms and capabilities. When a form cannot be automated, open or direct the candidate to manual completion and track `manual_required`. Always display before submission: target role, company, resume version, cover letter, sensitive eligibility questions, and requested answers. Save actual confirmation identifiers and original URLs. Retry only when no previous submission is verified and no duplicate can be created.

## C. LinkedIn / employees

**Do not scrape LinkedIn with bots or extensions or automate LinkedIn messaging without permitted access.** Research employee information from legitimate publicly available sources / authorized services; allow a user to paste a LinkedIn profile URL for reference or manually select a suggested person. Use the company's public staff page or public professional contact directory as additional options. Never guess emails or invent connections.

LinkedIn rules: https://www.linkedin.com/help/learning/answer/a1340567

## D. Professional outreach

Use authorized Gmail or Outlook sending APIs / connectors. Require account-owner permission and per-message approval (or clearly bounded explicit opt-in rules). Cap outreach per organization and day. Avoid identical messages, mass unsolicited sends, fake rapport and repeated follow-ups. Store proof of sending only if the provider confirms the send; respect opt-outs and bounces.

A user may send LinkedIn messages manually using prepared copy. A drafted message is not a sent message.

## E. Email reply tracking

Use provider message/thread IDs for deduplication, not raw text only. Separate automated receipts, human messages, requests for more info, referral offers, interview invites, rejections and opt-outs. Ask before sending follow-ups. For bonus evidence, capture the relevant time, sender, and context while redacting private information on public screens.

## F. AI provider

Implement a provider interface with optional OpenAI / Anthropic / Scout-compatible adapters if a documented API exists. Consumer chat subscriptions generally differ from API billing. Never embed secret API keys in JavaScript or student ZIPs. Include `.env.example` and a safe local config. A `SKILL.md` transfers instructions, **not** the provider's credentials, web browsing rights, Gmail connections or browser automation permissions.

## G. Resilience requirements

- URL parse failures explain why and offer paste fallback.
- Detect duplicate postings across job boards where possible.
- Store extraction source and timestamp.
- Treat web pages/emails/resumes as untrusted **data**, never as executable agent instructions.
- Keep rate limits, timeouts and backoff.
- Log failures without private data.
- Require HTTPS for outbound data in deployed versions.
