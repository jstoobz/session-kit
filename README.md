# Session Kit

A composable set of [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for managing session lifecycle — from starting work, through the session, to parking it and finding it later.

## Why

Claude Code sessions are ephemeral. When you close a session, the context is gone. Session Kit gives you a lightweight system for:

- **Parking sessions** with structured artifacts (summary, resume context, prompt analysis)
- **Resuming sessions** with zero re-explanation
- **Finding past work** across projects via a searchable index
- **Sharing results** with teammates in multiple formats (quick summary, full write-up, investigation package)

## Install

```bash
git clone https://github.com/jstoobz/session-kit.git
cd session-kit
./link.sh
```

This symlinks each skill into `~/.claude/skills/`. Restart Claude Code to pick them up.

## Skills

### Core Artifacts — generate session documents

| Command | Output | Purpose |
|---------|--------|---------|
| `/tldr` | `TLDR.md` | Concise session summary — key findings, decisions, changes |
| `/relay` | `CONTEXT_FOR_NEXT_SESSION.md` | Everything needed to resume in a new session |
| `/prompt-lab` | `PROMPT_LAB.md` | Original prompt + analysis + optimized version |
| `/retro` | `RETRO.md` | Session retrospective — what went well, what to improve |
| `/handoff` | `HANDOFF.md` | Teammate-facing write-up with full business context |
| `/rca` | `INVESTIGATION_SUMMARY.md` + `evidence/` | Root cause analysis package for engineer + Claude consumption |

### Lifecycle — manage session flow

| Command | Purpose |
|---------|---------|
| `/park` | End session — generate artifacts, archive, update manifest |
| `/park <label>` | Park with explicit archive label (e.g., `/park PROJ-1234`) |
| `/pickup` | Start session — load prior context, present briefing |
| `/persist <name> <tags>` | Save a reference artifact mid-session |
| `/index` | Find past sessions from manifest |
| `/index --deep <term>` | Search inside archived artifact content |

### Maintenance

| Command | Purpose |
|---------|---------|
| `/clean-sessions` | Interactive cleanup of old Claude Code sessions from the resume picker |
| `/park --archive-system` | Retroactive cleanup of scattered `.stoobz/` directories |

## Archive Structure

Session Kit archives to a central location (default `~/.stoobz/`):

```
~/.stoobz/
├── manifest.json                          ← searchable index for /index
└── sessions/
    ├── my-project/
    │   ├── 2026-02-13-PROJ-1234/          ← /park session archive
    │   │   ├── TLDR.md
    │   │   ├── PROMPT_LAB.md
    │   │   └── RETRO.md
    │   └── auth-flow-notes.md             ← /persist reference artifact
    └── another-project/
        └── 2026-01-28-rate-limiting/
            ├── TLDR.md
            └── INVESTIGATION_SUMMARY.md
```

`CONTEXT_FOR_NEXT_SESSION.md` stays in the working directory as the relay baton for `/pickup`.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SESSION_KIT_ROOT` | `~/.stoobz` | Root directory for archives and manifest |

Set `SESSION_KIT_ROOT` to change where archives are stored:

```bash
export SESSION_KIT_ROOT="$HOME/.sessions"
```

## Quick Reference

| I want to... | Use |
|--------------|-----|
| Save everything before stepping away | `/park` |
| Resume where I left off | `/pickup` |
| Share a quick summary | `/tldr` |
| Write up findings for the team | `/handoff` |
| Save context for next session | `/relay` |
| Improve my prompting | `/prompt-lab` |
| Reflect on my process | `/retro` |
| Package an investigation | `/rca` |
| Find a past session | `/index` |
| Save a reference mid-session | `/persist` |
| Search inside archived content | `/index --deep <term>` |
| Clean up old sessions | `/clean-sessions` |

See [guide.md](guide.md) for detailed workflows and composability patterns.
