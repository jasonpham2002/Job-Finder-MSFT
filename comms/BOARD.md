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
| _None_ | — | — | — | Owner A released locks after completing `A-05` (`H-03` posted). |

**Current Blockers:** _None — Foundation (`S-01`), `A-01..A-05`, and handoffs `H-01..H-03` complete._

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
| `A-06` | *(Optional)* Headed Playwright HITL Autofill | `TODO` | `A-03` | `app/adapters_pipeline.py` |
| `A-07` | Unit tests (`tests/test_pipeline.py`) + Live Submissions | `TODO` | `A-03` | `tests/test_pipeline.py` |

### Owner B Queue (`plans/OWNER_B_WORKBOOK.md`)
| ID | Task | Status | Depends On | Target Files |
|---|---|---|---|---|
| `B-01` | Gmail OAuth primary + Outlook contract `OutreachAdapter` | `TODO` | `S-01` | `app/adapters_outreach.py`, `app/routes_outreach.py`, `web/outreach.js` |
| `B-02` | `InboxAdapter` + Thread Reply Classifier + `fictional_inbox` sim | `TODO` | `S-01` (enhanced by `A-01` `H-02`) | `app/adapters_outreach.py`, `app/routes_outreach.py`, `web/outreach.js` |
| `B-03` | **D4** Artifact-First Public Contact Research + 3-Sentence Anti-Flattery Drafts | `TODO` | `S-01`, `A-01` (`H-02`) | `app/adapters_outreach.py`, `app/routes_outreach.py`, `web/outreach.js` |
| `B-04` | Cooldown/Opt-Out Firewall + **D2** Callback Cheat Sheet Trigger UI | `TODO` | `B-02`, `A-05` (`H-03`) | `app/routes_outreach.py`, `web/outreach.js` |
| `B-05` | Upgrade `skills/*/SKILL.md` + `prompts/*.md` + `sync_harness.py` | `TODO` | `A-05`, `B-04` | `skills/*/SKILL.md`, `prompts/*.md`, `.agents/skills/` |
| `B-06` | Computer B Clean-Environment Portability Test + `TEAM_HANDOFF_TEMPLATE.md` | `TODO` | `A-07`, `B-05` | `deliverables/TEAM_HANDOFF_TEMPLATE.md` |
| `B-07` | Unit tests (`tests/test_outreach.py`) + Live Outreach | `TODO` | `B-01`, `B-04` | `tests/test_outreach.py` |
