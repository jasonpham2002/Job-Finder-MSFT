---
description: Sync with the multi-agent Communication Board and check ownership before editing
---
# Workflow: Sync With Communication Board

1. Read `AGENTS.md`, `plans/TEAM_CHARTER.md`, and `comms/BOARD.md`.
2. Run `git status` and `git log -n 5 --oneline` to inspect recent teammate changes.
3. Check `comms/handoffs/` for any open handoffs directed to your owner role (`Owner A` or `Owner B`).
4. Check `comms/BOARD.md` "Active File Locks" and confirm none of the files you plan to edit are owned by the other teammate or frozen without an RFC in `comms/decisions/`.
5. Claim your task ID (`A-01..A-07` or `B-01..B-07`) in `comms/BOARD.md` by setting its status to `IN_PROGRESS` and listing the files you are editing.
