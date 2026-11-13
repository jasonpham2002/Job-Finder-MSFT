# Six Portable Agent Skills

Each folder contains a `SKILL.md` with Agent Skills YAML frontmatter (`name`, `description`). These are reusable **instructions** rather than tools or credentials.

Run `python scripts/export_skills.py` to produce individual import ZIPs and a bundle. For Claude Code, copy the desired folder under `.claude/skills/`; for supported Claude AI import surfaces, upload an individual skill ZIP. For ChatGPT/Codex use the supported skill/plugin installation path, or use the text in project instructions when native import is unavailable. A plain language model cannot submit applications without separate permitted tools, authentication and approval.
