# Start Here — Student Instructions

## Your mission

Build **one transferable AI career assistant** that works from a URL for **LinkedIn, Indeed, Workday, Greenhouse, Lever, ZipRecruiter, or an unfamiliar company career page**, not a tool hard-coded for one job board.

By the end of the hackathon, aim to **submit 10 verified, relevant, real applications** using an authorized candidate's actual resume and consent; **prepare/send up to 10 personalized, approved professional introductions**; and demonstrate a dashboard tracking applications and responses. A genuine reply or interview invitation by the end of the day earns bonus points. You **cannot guarantee replies**, and automated acknowledgments do not count.

### Main workflow

1. Candidate uploads their resume and declares preferences (roles, locations, salary, remote, etc.).
2. User pastes a job posting URL **from any job website** OR asks for recommended roles.
3. Agent extracts and normalizes job details; if blocked, asks for pasted description rather than bypassing access controls.
4. Agent compares job requirements against actual candidate evidence; flags gaps.
5. Agent produces a fact-checked, tailored resume and optionally a cover letter.
6. Agent finds professional contacts (recruiter, manager, relevant employee) from legitimate public or authorized sources, noting source and confidence.
7. Agent drafts thoughtful, individual LinkedIn/email outreach with approval and frequency limits.
8. Agent completes supported job application steps with authenticated user authorization, requests approval, submits, and captures actual confirmation.
9. Agent tracks application and outreach status; classifies inbox replies (human, automated receipt, rejection, interview) using authorized email access.
10. Agent exports **skills, prompts, code, tests, and setup instructions** to run independently on a second computer.

## Non-negotiable constraints

- **10 real, verified applications** is the primary goal. Demo submissions **do not count**.
- The agent never invents qualifications, identity, work authorization, or employment history.
- Job-site access must comply with site restrictions. Never bypass CAPTCHAs or anti-bot controls. No unauthorized LinkedIn scraping or automatic messaging.
- Explicit authorization is required for submissions/outreach. Default to review before submit/send; show what will go out.
- Do not guess contact email addresses, scrape private data, spam people, or send to fictional sample contacts.
- The ZIP must work for a new judge with no secrets from the developer's machine.
- If a site lacks a supported adapter, report it and offer manual completion. Do not mark it submitted.

## Quick start

```bash
python -m app.server
# open http://127.0.0.1:8765
```

No third-party Python packages required for the **offline starter**. Read `README.md` and `docs/ARCHITECTURE.md` to extend it.

## Suggested team roles

- **Agent/workflow lead:** prompt quality, factuality, evaluation.
- **Integrations lead:** job URL extraction, approved browser/application adapter.
- **Outreach lead:** professional contact research, messages, inbox classification.
- **UI/portability lead:** dashboard, export, docs, second-computer test.

## Final submission

Deliver `Final_JobFinder_<TeamName>.zip`, a short demo, 10 verified confirmations if achieved, 10 approved outreach records if achieved, and the completed `deliverables/TEAM_HANDOFF_TEMPLATE.md`. A team must report shortfalls honestly; claiming mock submissions as real is a disqualifying reliability issue.
