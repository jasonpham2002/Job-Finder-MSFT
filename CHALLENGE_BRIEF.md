# Hackathon Challenge 4 — Universal Job Finder, Auto Apply & Networking Agent

## The big idea

**Upload one resume → paste any job URL → research → tailor resume → apply → find professional contacts → send personalized introductions → track responses → export the agent.**

The solution should be useful after the hackathon. It must work with a different candidate, a different computer, and a previously unseen job posting URL.

## User stories / acceptance criteria

### A. Universal job input
- Accept LinkedIn, Indeed, Workday, Greenhouse, Lever, ZipRecruiter and employer careers URLs as **candidate inputs**, not guaranteed automated destinations.
- Support direct paste of job description if a website is login-gated, blocks access, relies on JavaScript, or prohibits automation.
- Extract title, employer, location, salary if disclosed, responsibilities, requirements, and original URL. Show source and extraction confidence.
- Support autonomous discovery of 10 distinct active roles using permitted sources; validate posting dates / status where possible; deduplicate.

### B. Resume tailoring and employee intelligence
- Upload PDF, DOCX and TXT resumes in the completed solution.
- Identify verified accomplishments and skills before drafting; never add unsupported experience.
- Rewrite each resume specifically for the role and generate an optional cover letter.
- Research publicly disclosed backgrounds of people in similar jobs to identify useful keywords and optional skills to learn — not to impersonate employees or invent claims.
- Export formatted PDF and DOCX resumes in the final product.

### C. Applications
- Queue at least 10 relevant roles, with rationale and fit scores clearly labeled as estimates.
- Provide user review of job, resume and answers; protect sensitive questions such as sponsorship, veteran status and disability from invented answers.
- Use an approved integration or supported browser workflow; handle logins and challenges through the human user, never bypass controls.
- Capture employer/ATS confirmation ID, date/time, URL or screenshot where permissible; report unknown outcome as unknown, not success.
- Avoid double applications and keep audit history.

### D. Professional networking
- Identify up to three relevant people per job (recruiter, hiring manager, role peer), using legitimate public information / authorized tools.
- Show name, title, company, professional profile link, source, verification status, and reason to contact.
- Locate a **publicly listed professional** email when available; never guess or infer private addresses as verified.
- Prepare individualized emails and LinkedIn messages, then send only through permitted channels with explicit approval and respectful limits.
- Keep opt-outs; avoid repeatedly contacting the same person.

### E. Replies, pipeline, follow-ups
- Track application, outreach, interview and referral statuses in dashboard.
- Connect authorized Gmail / Outlook source; detect human replies vs auto receipts, offers, rejections, and interview requests.
- Summarize threads and draft context-specific follow-up for approval.
- Track genuine recruiter reply, referral and interview bonus evidence without guaranteeing results.

### F. Transferable deliverable
- Export one ZIP with application source, setup files, environment template, schemas, tests, documentation and portable Agent Skills.
- Another judge should install on another computer, configure their own credentials, upload another resume, paste an unfamiliar URL, get a tailored resume and outreach draft, and complete a test application.
- Export core logic into Claude, ChatGPT/Codex or another supported skill-capable agent where possible; platform-specific permissions and connectors need independent setup.

## Timebox

**4–6 hours to build.** Prioritize a complete end-to-end user flow. Mandatory outcomes remain ambitious; score honestly and demo fallback workflows if a site cannot be automated legally or within the timebox.

## Success metrics

- Target: **10 independently verified real job submissions**.
- Target: **10 individualized professional outreach messages sent with authorization** (or accurately logged as drafts where sending unavailable).
- Bonus: genuine nonautomated reply, referral, or confirmed interview invitation before judges' cutoff.
- Portability: reproducible import on fresh computer; reusable skills, prompts and workflow instructions.

## What is explicitly NOT a success

Ten fake jobs, “submit clicked” without confirmation, bulk unsolicited copy-paste spam, fabricated resume experience, scraped private LinkedIn addresses, duplicate applications, or a solution that only works in its creator's AI chat.
