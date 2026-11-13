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
| _None_ | — | — | — | Owner A queue (`A-01..A-07`) complete; all locks released (`H-04` posted). |

**Current Blockers:** _None — Foundation (`S-01`), entire Owner A queue (`A-01..A-07`), and handoffs `H-01..H-04` complete._

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
| `A-02` | `JobDiscoveryAdapter` (Greenhouse/Lever/Ashby) + **D1** Pre-Flight Shield | `DONE` | `A-01` | `app/engine.py`, `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` (36/36 tests passing; Serper smoke test OK) |
| `A-03` | **D3** Co-Pilot Packet + Sensitive-Field Gate + SHA-256 Receipts | `DONE` | `A-01` | `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` (39/39 tests passing) |
| `A-04` | **D2** Voice-Preserving Anti-Slop Tailor + ATS Plain-Text Preview | `DONE` | `A-01` | `app/engine.py`, `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` (44/44 tests passing; live Gemini `gemini-3.8-flash` smoke test OK) |
| `A-05` | **D5** Gap-to-Proof Bridge + **D2** Callback Cheat Sheet Snapshot | `DONE` | `A-04` | `app/engine.py`, `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` · See `comms/handoffs/H-03-gap-bridge-callback-packet.md` (48/48 tests passing; live Gemini `gemini-3.8-flash` smoke test OK) |
| `A-06` | *(Optional)* Headed Playwright HITL Autofill | `DONE` | `A-03` | `app/adapters_pipeline.py`, `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` · Graceful D3 Co-Pilot fallback; sensitive fields strictly locked |
| `A-07` | Unit tests (`tests/test_pipeline.py`) + Live Submissions Readiness | `DONE` | `A-03`, `A-05`, `A-06` | `app/routes_pipeline.py`, `web/pipeline.js`, `tests/test_pipeline.py` · See `comms/handoffs/H-04-owner-a-complete.md` (51/51 tests passing; 10-job batch + readiness scorecard ready for human live submissions) |

### Owner B Queue (`plans/OWNER_B_WORKBOOK.md`)

QA (2026-11-13): 67/67 combined unit + loopback HTTP tests passed (`test_engine`, `test_contracts`, `test_portability`, `test_pipeline`, `test_outreach`, `test_api`). Six skill mirrors matched. Clean-export ZIP package validation passed without `.env` or local SQLite database.

| ID | Task | Status | Depends On | Target Files |
|---|---|---|---|---|
| `B-01` | Gmail OAuth primary + Outlook contract `OutreachAdapter` | `DONE` | `S-01` | `app/adapters_outreach.py`, `app/routes_outreach.py`, `web/outreach.js` · Full UI Delivery Studio (Stage -> Approve -> Send -> Confirm Manual Sent) wired; desktop OAuth verified on user-controlled inbox. |
| `B-02` | `InboxAdapter` + Thread Reply Classifier + `fictional_inbox` sim | `DONE` | `S-01` | `app/adapters_outreach.py`, `app/routes_outreach.py`, `web/outreach.js` · Expanded natural recruiter reply classification + `TEST ONLY` simulation with D2 callback preview. |
| `B-03` | **D4** Artifact-First Public Contact Research + 3-Sentence Anti-Flattery Drafts | `DONE` | `S-01`, `A-01` (`H-02`) | `app/adapters_outreach.py`, `app/routes_outreach.py`, `web/outreach.js` · SSRF-safe redirects, JSON-LD + HTML team card + blog author metadata extraction, user-verified excerpt fallback, and overlap-grounded 3-sentence drafts. |
| `B-04` | Cooldown/Opt-Out Firewall + **D2** Callback Cheat Sheet Trigger UI | `DONE` | `B-02`, `A-05` (`H-03`) | `app/routes_outreach.py`, `web/outreach.js` · Opt-out & configurable cooldown enforced; formatted 30-second Callback Cheat Sheet drawer integrated with Owner A `H-03` snapshots. |
| `B-05` | Upgrade `skills/*/SKILL.md` + `prompts/*.md` + `sync_harness.py` | `DONE` | `A-05`, `B-04` | `skills/*/SKILL.md`, `.agents/skills/*/SKILL.md`, `prompts/*.md` · All 6 skills and prompts synchronized and packaged. |
| `B-06` | Computer B Clean-Environment Portability Test + `TEAM_HANDOFF_TEMPLATE.md` | `DONE` | `A-07`, `B-05` | `deliverables/TEAM_HANDOFF_TEMPLATE.md`, `comms/handoffs/H-B03-B07-owner-b.md`, `comms/reviews/R-B03-B07-local-review.md` · Clean export ZIP validated (`68` files + skill archives). |
| `B-07` | Unit tests (`tests/test_outreach.py`) + Live Outreach Readiness | `DONE` | `B-01`, `B-04` | `tests/test_outreach.py` (16 outreach tests; 67/67 total suite passing; live outreach `0/10` awaiting human sends). |
