---
name: sweep
description: Interactive cleanup of old Claude Code sessions from the resume picker. Use when the user says "/sweep", "sweep sessions", "too many sessions", "session picker is cluttered", or wants to remove old/unused sessions. Runs an interactive Python script that categorizes and selectively deletes sessions.
---

# Sweep

Interactive cleanup of Claude Code sessions from the resume picker.

## Process

1. Run the cleanup script:

```bash
python3 "$(dirname "$(readlink -f ~/.claude/skills/sweep)")/scripts/sweep.py"
```

If the above fails (e.g., no `readlink -f` on macOS), fall back to:

```bash
python3 ~/.claude/skills/sweep/scripts/sweep.py
```

2. The script will:
   - List all projects with sessions
   - Let the user select which project to clean
   - Categorize sessions into cleanup groups:
     - **Old & unnamed** — auto-selected (safe to remove)
     - **Old & tiny** (<=2 messages) — auto-selected
     - **Tiny & unnamed** — auto-selected
     - **Old but named** — shown but NOT auto-selected (user reviews)
   - Present each category interactively for toggle selection
   - Confirm before deleting

3. For each deleted session, removes both the `.jsonl` transcript and session directory.

## Arguments

| Flag               | Default     | Purpose                                            |
| ------------------ | ----------- | -------------------------------------------------- |
| `--max-age DAYS`   | 14          | Days before a session is considered "old"          |
| `--min-messages N` | 2           | Minimum messages for a session to be "significant" |
| `--dry-run`        | false       | Preview without deleting                           |
| `--project PATH`   | interactive | Skip project selection                             |

## What Gets Preserved Elsewhere

Deleting sessions does NOT affect:

- Auto memory (`MEMORY.md`) — persists independently
- Session Kit artifacts (`TLDR.md`, `CONTEXT_FOR_NEXT_SESSION.md`, etc.) — in `.stoobz/` dirs
- Project CLAUDE.md files
- Skills and configurations

The only thing lost is the raw conversation transcript (`.jsonl` file).

## Rules

- **Always interactive** — never auto-delete without confirmation
- **Named sessions are protected** — shown in review but not auto-selected
- **Dry-run first** — suggest `--dry-run` if the user seems uncertain
