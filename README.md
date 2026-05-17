# Session Kit

A composable set of [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for managing session lifecycle — from starting work, through the session, to parking it and finding it later.

## Why

Claude Code sessions are ephemeral. When you close a session, the context is gone. Session Kit gives you a lightweight system for:

- **Priming repos** with expert skills and context files for productive sessions
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

This symlinks each skill into `~/.claude/skills/` and the `sk` dispatcher binary into `~/.local/bin/sk`. Restart Claude Code to pick up the new skills.

The `sk` binary is the backing implementation for the migrated skills (`/checkin`, `/park`, `/tldr`, `/relay`, `/hone`, `/retro`, `/handoff`, `/rca`, `/persist`) — each SKILL.md is a thin orchestrator that invokes a `sk <subcommand>`. Run `sk --help` for the full subcommand reference. `~/.local/bin` must be on your `PATH`.

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The `bin/sk` shebang invokes `uv run` to manage its own dependencies (typer, filelock) — no system-wide install needed.

## Skills

### Registration — register the session before any artifact is written

| Command | Purpose |
|---------|---------|
| `/checkin` | Register the current Claude Code session in `manifest.json`, pre-allocate the durable archive dir + ledger. Invoked silently as a precondition by every artifact-producing skill below. |

### Core Artifacts — generate session documents

| Command | Output | Purpose |
|---------|--------|---------|
| `/tldr` | `.stoobz/TLDR.md` | Concise session summary — key findings, decisions, changes |
| `/relay` | `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` | Everything needed to resume in a new session |
| `/hone` | `.stoobz/HONE.md` | Original prompt + analysis + optimized version |
| `/retro` | `.stoobz/RETRO.md` | Session retrospective — what went well, what to improve |
| `/handoff` | `.stoobz/HANDOFF.md` | Teammate-facing write-up with full business context |
| `/rca` | `.stoobz/INVESTIGATION_SUMMARY.md` + `.stoobz/evidence/` | Root cause analysis package for engineer + Claude consumption |

### Lifecycle — manage session flow

| Command | Purpose |
|---------|---------|
| `/park` | End session — generate artifacts, archive, update manifest |
| `/park <label>` | Park with explicit archive label (e.g., `/park PROJ-1234`) |
| `/pickup` | Start session — load prior context, present briefing, inherit chain metadata from the relay baton |
| `/persist <name> <tags>` | Save a reference artifact mid-session to `.stoobz/` |
| `/checkpoint` | Synthesize selected chain nodes into a new starting point (branch chain) |
| `/index` | Find past sessions from manifest |
| `/index --deep <term>` | Search inside archived artifact content |

### Project Setup — create permanent expert knowledge

| Command | Purpose |
|---------|---------|
| `/prime` | Analyze repo, create expert skills + context files |
| `/prime --refresh` | Update stale skills based on what changed |

### Maintenance

| Command | Purpose |
|---------|---------|
| `/sweep` | Interactive cleanup of old Claude Code sessions from the resume picker |
| `/park --archive-system` | Retroactive cleanup of scattered `.stoobz/` directories (pending re-migration; see `park/SKILL.md`) |

## Archive Structure

Session Kit archives to a central location (default `~/.stoobz/`):

```
~/.stoobz/
├── manifest.json                          ← searchable index for /index
└── sessions/
    ├── my-project/
    │   ├── <session-id>-active/           ← /checkin pre-allocates this for live sessions
    │   │   ├── .session-artifacts.json    ← ledger of artifact writes
    │   │   └── (in-flight artifacts)
    │   ├── 2026-02-13-PROJ-1234/          ← /park renames -active/ to date-label form
    │   │   ├── .session-artifacts.json
    │   │   ├── TLDR.md
    │   │   ├── HONE.md
    │   │   └── RETRO.md
    │   └── auth-flow-notes.md             ← /persist reference artifact
    └── another-project/
        └── 2026-01-28-rate-limiting/
            ├── TLDR.md
            └── INVESTIGATION_SUMMARY.md
```

During a session, every artifact is written **directly** to the durable `<session-id>-active/` directory (via `sk write-artifact`) and **copied** to `./.stoobz/` for in-session discovery. `/park` renames the active directory to its final `<date>-<label>/` form, flips the manifest entry from `active` to `archived`, and leaves `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` as the relay baton for `/pickup`.

This is the **durable-first** protocol — if the session terminates abnormally, the artifacts are already in the central archive. See [`write-artifact-protocol.md`](write-artifact-protocol.md) for the contract artifact-emitting skills follow.

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
| Register this session before doing anything | `/checkin` (also auto-fires under every artifact skill) |
| Set up expert skills for a new repo | `/prime` |
| Update stale expert skills | `/prime --refresh` |
| Save everything before stepping away | `/park` |
| Resume where I left off | `/pickup` |
| Branch a new chain from selected past sessions | `/checkpoint` |
| Share a quick summary | `/tldr` |
| Write up findings for the team | `/handoff` |
| Save context for next session | `/relay` |
| Improve my prompting | `/hone` |
| Reflect on my process | `/retro` |
| Package an investigation | `/rca` |
| Find a past session | `/index` |
| Save a reference mid-session | `/persist` |
| Search inside archived content | `/index --deep <term>` |
| Clean up old sessions | `/sweep` |

See [guide.md](guide.md) for detailed workflows and composability patterns. The `sk` CLI also exposes machine-readable surfaces (`sk checkin --json`, `sk write-artifact`, `sk park-finalize --json`) for scripting or testing — run `sk --help` for the full subcommand list.
