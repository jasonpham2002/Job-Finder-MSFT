# Live Team & Agent Communication Board

## Team Roster & Harnesses
| Role | Teammate Name / Handle | Primary Harnesses | Branch Prefix |
|---|---|---|---|
| **Owner A** (Core Pipeline, AI Tailoring & Apply) | _Fill in Teammate A_ | Antigravity / Codex | `feat/a-*` |
| **Owner B** (Contacts, Outreach, Inbox & Portability) | _Fill in Teammate B_ | Antigravity / Codex | `feat/b-*` |

## Hackathon Evidence Scoreboard
| Metric | Current | Target | Notes |
|---|---:|---:|---|
| Verified real applications | `0` | `10` | Must have external confirmation ID/email/screenshot |
| Approved real outreach sent | `0` | `10` | Unique, artifact-grounded, opt-out checked |
| Genuine human replies | `0` | Bonus (+20) | Auto-receipts excluded |
| Confirmed referrals / interviews | `0` | Bonus (+30/+50) | |
| Computer B clean ZIP verified | `no` | `yes` | Required by `docs/ACCEPTANCE_TESTS.md` |

---

## Active File Locks & Blockers
| File / Scope | Locked By | Task ID | Since | Notes |
|---|---|---|---|---|

**Current Blockers:** _None — Foundation (`S-01`) complete via `comms/handoffs/H-01-foundation-ready.md`._

---

## Task Board

### Shared Foundation
| ID | Task | Owner | Status | Notes / Handoff |
|---|---|---|---|---|
| `S-01` | Multi-agent workspace, harness configs, schemas, DB migrations, modular seams | Shared | `DONE` | See `comms/handoffs/H-01-foundation-ready.md` |

### Owner A Queue (`plans/OWNER_A_WORKBOOK.md`)
| ID | Task | Status | Depends On | Target Files |
|---|---|---|---|---|
| `A-01` | Unified `ModelAdapter` (OpenAI/Gemini/Anthropic) + `ResumeFileAdapter` (PDF/DOCX) | `DONE` | `S-01` | `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` · See `comms/handoffs/H-02-model-resume-adapters.md` |
| `A-02` | `JobDiscoveryAdapter` (Greenhouse/Lever/Ashby) + **D1** Pre-Flight Shield | `TODO` | `A-01` | `app/engine.py`, `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js` |
| `A-03` | **D3** Co-Pilot Packet + Sensitive-Field Gate + SHA-256 Receipts | `TODO` | `A-01` | `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js` |
| `A-04` | **D2** Voice-Preserving Anti-Slop Tailor + ATS Plain-Text Preview | `TODO` | `A-01` | `app/engine.py`, `app/adapters_pipeline.py`, `web/pipeline.js` |
| `A-05` | **D5** Gap-to-Proof Bridge + **D2** Callback Cheat Sheet Snapshot | `TODO` | `A-04` | `app/routes_pipeline.py`, `web/pipeline.js` |
| `A-06` | *(Optional)* Headed Playwright HITL Autofill | `TODO` | `A-03` | `app/adapters_pipeline.py` |
| `A-07` | Unit tests (`tests/test_pipeline.py`) + Live Submissions | `TODO` | `A-03` | `tests/test_pipeline.py` |

### Owner B Queue (`plans/OWNER_B_WORKBOOK.md`)

QA (2026-11-13): 13/13 existing tests passed with local loopback access. Six skill mirrors matched. The `TEST ONLY` inbox simulation correctly classified all three fixture messages. Package validation passed on a clean local copy without `.env` or the local database. Computer B and live outreach remain unverified.

| ID | Task | Status | Depends On | Target Files |
|---|---|---|---|---|
| `B-01` | Gmail OAuth primary + Outlook contract `OutreachAdapter` | `DONE` | `S-01` | 21 tests passed. On 2026-11-13, desktop OAuth completed and Gmail returned a message ID for one approved test sent through the adapter to a user-controlled inbox. The test is excluded from the outreach scoreboard. |
| `B-02` | `InboxAdapter` + Thread Reply Classifier + `fictional_inbox` sim | `DONE` | `S-01` | All three offline fixtures classified correctly. 24 tests passed, including simulated Gmail sync and deduplication. Live Gmail sync awaits separate read-only OAuth. |
| `B-03` | **D4** Artifact-First Public Contact Research + 3-Sentence Anti-Flattery Drafts | `IN_PROGRESS` | `S-01`, `A-01` (`H-02`) | Public employer JSON-LD research, source cards, manual queries and artifact drafts implemented. H-02 integrated. Live Gemini artifact drafting passed with synthetic data. Live contact-source verification pending. |
| `B-04` | Cooldown/Opt-Out Firewall + **D2** Callback Cheat Sheet Trigger UI | `IN_PROGRESS` | `B-02`, `A-05` (`H-03`) | Opt-out and configurable cooldown tested. User links replies to confirmed applications. Exact snapshot tested with fixture. H-03 live snapshot producer pending. |
| `B-05` | Upgrade `skills/*/SKILL.md` + `prompts/*.md` + `sync_harness.py` | `IN_PROGRESS` | `A-05`, `B-04` | Six skills and prompts updated. Mirrors and ZIPs verified. Second harness execution pending. |
| `B-06` | Computer B Clean-Environment Portability Test + `TEAM_HANDOFF_TEMPLATE.md` | `IN_PROGRESS` | `A-07`, `B-05` | Release ZIP inspected and extracted locally. Package validation and 42 tests passed after A-01 integration, including PDF/DOCX fixtures. Computer B and independent review pending. |
| `B-07` | Unit tests (`tests/test_outreach.py`) + Live Outreach | `IN_PROGRESS` | `B-01`, `B-04` | Outreach tests cover opt-out, cooldown, deduplication, auto-receipts and artifact validation. Approved recruiting outreach remains 0/10. |
