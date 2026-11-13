# Portability Guide — Computer A to Computer B and Between AI Providers

## Two separate types of portability

**Skill portability:** `SKILL.md` + prompts + workflows move agent instructions across compatible AI products. The skill alone cannot sign into an email service, perform browser automation, or magically install site connectors.

**Application portability:** source code, dependencies, database migrations, setup scripts, tests and templates let a judge run the software on another computer. Integrations require new account connections and permissions.

## Step 1 — Export on Computer A

```bash
python -m unittest discover -s tests -v
python scripts/validate_package.py
python scripts/export_skills.py
python scripts/export_handoff.py
```

This produces `exports/*.zip` for individual skills and a combined skills ZIP. To hand off the **whole working application**, use `exports/jobfinder-complete-portable-handoff.zip`. Extend `scripts/export_handoff.py` allowlists if adding new reusable source files. Never include local databases, real user files, `.env`, cookies, credentials, caches, virtual environments or logs.

## Step 2 — Import on Computer B

1. Extract project files.
2. Install Python or listed dependencies / use your packaged installer.
3. Create a fresh local configuration using `config.example.json` and `.env.example`.
4. Supply credentials in the destination machine's secret store; connect the destination user's accounts legitimately.
5. Run the tests and start the app.
6. Upload a new judge-provided resume, paste an unseen job URL, prepare a tailored draft, find a contact and stage a sample application.
7. If demonstrating live actions, obtain permission and verify confirmation for each action.

## Step 3 — Skills on AI platforms

- **Claude / Claude Code:** portable `SKILL.md` directories can be imported/installed in supported surfaces; Claude AI supports upload of custom skill ZIPs on eligible plans. See https://support.claude.com/en/articles/12512180-use-skills-in-claude. Claude Code project skills can be placed under `.claude/skills/<skill-name>/SKILL.md`.
- **OpenAI / ChatGPT / Codex:** follows the Agent Skills format in supported surfaces. Feature eligibility varies by product and plan. For personal chat contexts without native installation, copy instructions into a Project and attach supporting files; that does not run the external application by itself. See https://help.openai.com/en/articles/20001066-skills-in-chatgpt and https://agentskills.io/specification.
- **Scout:** ambiguous product name; verify which Scout you use and whether it accepts Agent Skills, plain-text prompts, API-based tool calls, or MCP. Do **not** promise drop-in import without checking its interface.

## Acceptance standard

- Skills load in at least one supported AI environment and generate the same structured outputs from supplied test data.
- Whole software starts on a second computer without the developer's accounts.
- All functionality which needs external services has documented re-authentication steps.
- No hardcoded absolute file paths, API keys or developer-specific browser profiles.
- The judge can explain which functions are live versus test-only.

## Important portability caveat

The student should not claim that ChatGPT, Claude and Scout are interchangeable execution environments. The prompts and data formats can often transfer; **tool execution and account permissions are separate**. Keep adapters modular, and report provider-specific constraints.
