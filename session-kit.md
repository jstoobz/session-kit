# Session Kit

A composable set of Claude Code skills for managing session lifecycle — from starting work, through the session, to parking it and sharing results.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SESSION_KIT_ROOT` | `~/.stoobz` | Root directory for archives and manifest |

All skills resolve the archive root at runtime: if `SESSION_KIT_ROOT` is set, use it; otherwise default to `~/.stoobz`. All `~/.stoobz/` paths in this document and individual skill docs refer to the resolved root.

## Skills

### Core Artifacts

| Command       | Output                                                              | Purpose                                                                                                                                                                        |
| ------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/tldr`       | `TLDR.md`                                                           | Concise session summary for sharing with engineers. Key findings, decisions, changes, open items. 2-minute read max.                                                           |
| `/relay`      | `CONTEXT_FOR_NEXT_SESSION.md`                                       | Everything Claude needs to resume in a new session. Optimized for machine consumption — paths, branch state, decisions, next steps, auto-detected skills to load.                            |
| `/hone` | `HONE.md`                                                     | Captures your original prompt verbatim, analyzes its effectiveness, generates an optimized version, and provides coaching tips. Builds prompt engineering intuition over time. |
| `/retro`      | `RETRO.md`                                                          | Session retrospective — what went well, what took longer than expected, what to do differently. Tracks recurring patterns across sessions.                                     |
| `/handoff`    | `HANDOFF.md`                                                        | Teammate-facing write-up with full business context, evidence, recommendations, and links. No Claude artifacts — pure human-to-human communication.                            |
| `/rca`        | `INVESTIGATION_SUMMARY.md`, `INVESTIGATION_CONTEXT.md`, `evidence/` | Root cause analysis package — quick-scan summary + Claude-droppable deep context + raw evidence. Designed for engineer + Claude consumption without any skill setup.           |

### Project Setup

| Command                | Output                                                            | Purpose                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `/prime`                 | `.claude/skills/*/SKILL.md`, `.claude/commands/contexts/*.md`       | "Set up this repo." Analyzes codebase architecture, creates expert skills + feature/debug context files for all future sessions. |
| `/prime --refresh`       | _(updates existing skills)_                                        | "Things changed." Checks staleness, re-analyzes changed layers, updates skills surgically.                                      |

### Lifecycle Commands

| Command                | Output                                                            | Purpose                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `/park`                  | `TLDR.md`, `CONTEXT_FOR_NEXT_SESSION.md`, `HONE.md`          | "I'm stepping away." Generates all core artifacts, archives to `~/.stoobz/sessions/<project>/<date-label>/`. `CONTEXT_FOR_NEXT_SESSION.md` stays in cwd as relay baton. |
| `/park <label>`          | _(same as /park)_                                                  | Park with an explicit label for the archive directory (e.g., `/park PROJ-1234`).                                               |
| `/park --archive-system` | _(scans and archives)_                                             | Retroactive cleanup — finds scattered `.stoobz/` dirs and loose artifacts, archives full subtrees to `~/.stoobz/sessions/`. Flags: `--select` (default), `--all`, `--dry-run`, `--clean`. |
| `/retro`                 | `RETRO.md`                                                         | Session retrospective — what went well, what took longer, what to do differently. Can run anytime; `/park` archives it if present. |
| `/persist`               | `<name>.md` in `~/.stoobz/sessions/<project>/`                              | "Save this thing." Persists a reference artifact mid-session with tags for `/index` discovery.                                 |
| `/persist <name> <tags>` | `<name>.md` in `~/.stoobz/sessions/<project>/`                              | Persist with explicit name and tags: `/persist runbook playbook deployment`.                                                    |
| `/pickup`                | _(reads existing artifacts)_                                       | "I'm back." Loads prior session context and presents a briefing. The complement to `/park`.                                    |
| `/index`                 | _(displayed, not written)_                                         | "Where was that?" Reads `~/.stoobz/manifest.json` for fast lookup. Supports filtering by topic, tag, or project.              |
| `/index <filter>`        | _(displayed, not written)_                                         | Filter sessions — searches tags, summary, label, project, and branch (case-insensitive).                                      |
| `/index --deep <term>`   | _(displayed, not written)_                                         | Deep search — greps inside archived artifact content when manifest metadata isn't enough.                                      |

## Session Lifecycle

```
Setup                         Start                         During                        End
  |                             |                             |                            |
  v                             v                             v                            v
/prime                      /pickup                    /tldr (anytime)              /park
  Analyze codebase            Read artifacts              Quick summary               Generates:
  Create expert skills        Load skills                 for sharing                   TLDR.md
  Create contexts             Present briefing                                          CONTEXT_FOR_NEXT_SESSION.md
  (run once or --refresh)                              /handoff (anytime)                HONE.md
                                                          Full write-up               Archives to:
                                                          for teammates                 ~/.stoobz/sessions/<project>/<date>/
                                                                                      Updates manifest.json
                                                       /persist (anytime)
                                                          Save a reference            /retro (optional)
                                                          artifact mid-session          Process reflection
                                                          → ~/.stoobz/sessions/<project>/

Later
  |
  v
/index
  Fast manifest lookup
  Filter by tag/project
```

## Composability Flows

### New Repo Onboarding

```
First session:  /prime → creates expert skills + contexts
Every session:  /pickup → [work with expert skills loaded] → /park
Months later:   /prime --refresh → updates skills for architecture changes
```

### Solo Deep Dive (investigation, profiling, architecture review)

```
Session 1:  [do work] → /park
Session 2:  /pickup → [continue] → /park
Session 3:  /pickup → [wrap up] → /park + /retro
```

### Ticket Work (Jira-driven features and bugs)

```
/ticket PROJ-XXXXX → [implement] → /park
Next session: /pickup → [finish] → /handoff + /park
```

### Sharing with Team

```
[complete investigation] → /tldr      (quick share in Slack)
                         → /handoff   (full context for PR review or pairing)
                         → /rca       (investigation package — teammate + their Claude pick it up)
```

### Production Investigation (debug → package → hand off)

```
Session 1:  [investigate] → /rca       (package findings + evidence for teammate)
                          → /park      (save your own session context too)
Teammate:   [drop INVESTIGATION_CONTEXT.md path into Claude] → review → verify → fix
```

### Prompt Honing Loop

```
Session 1:  [work from initial prompt] → /hone
Session 2:  [paste optimized prompt from HONE.md] → [work] → /hone
            Compare: is the optimized prompt actually better?
```

### End of Day Dump

```
/park                    (saves context + summary + prompt analysis → archives)
/retro                   (reflect on what worked)
/handoff                 (if teammates need to pick up tomorrow)
```

### Finding Past Work

```
/index                          → see all sessions from manifest
/index elixir                   → filter by tag
/index memory leak              → filter by summary/label
/index my-project               → filter by project
cd into source_dir → /pickup    → resume that work
```

### Retroactive Cleanup

```
/park --archive-system              → interactive picker (default --select)
/park --archive-system --dry-run    → show what would happen, no changes
/park --archive-system --all        → archive everything, no prompting
/park --archive-system --all --clean → archive + auto-remove originals
```

## File Existence Behavior

All artifact-generating skills check for existing files before writing:

- If the file exists, previous content is preserved under a timestamped "Previous" heading
- New content is added as the primary (top) section
- This creates a rolling history — latest first, older entries below
- Open items from previous sessions are carried forward (completed items checked off)

## Archive Convention

Session artifacts are archived to a central location for fast indexing and cross-project discovery:

```
~/.stoobz/
├── manifest.json                                ← fast index for /index
├── sessions/                                    ← all /park + /persist output
│   ├── my-project/
│   │   ├── 2026-02-13-PROJ-1234/               ← /park session archive
│   │   │   ├── TLDR.md
│   │   │   ├── HONE.md
│   │   │   └── RETRO.md
│   │   ├── 2026-02-10-auth-token-refresh/
│   │   │   └── ...
│   │   └── auth-flow-notes.md                   ← /persist reference artifact
│   ├── session-kit-lab/
│   │   └── 2026-02-13-archive-feature/
│   │       ├── TLDR.md
│   │       └── HONE.md
│   └── api-gateway/
│       └── 2026-01-28-rate-limiting/
│           ├── TLDR.md
│           ├── INVESTIGATION_SUMMARY.md
│           └── evidence/
├── prompts/                                     ← organic work (not managed by session-kit)
└── ...
```

- `CONTEXT_FOR_NEXT_SESSION.md` stays in source cwd during normal `/park` (relay baton for `/pickup`). In `--archive-system` mode, it gets archived too (old sessions nobody is picking up).
- `manifest.json` is the single source of truth for `/index`
- Archives are organized by project, then by date-label

## Quick Reference

| I want to...                            | Use                    |
| --------------------------------------- | ---------------------- |
| Set up expert skills for a new repo     | `/prime`               |
| Update stale expert skills              | `/prime --refresh`     |
| Save everything before stepping away    | `/park`                |
| Park with a specific label              | `/park <label>`        |
| Resume where I left off                 | `/pickup`              |
| Share a quick summary                   | `/tldr`                |
| Write up findings for the team          | `/handoff`             |
| Save context for my next session        | `/relay`               |
| Improve my prompting                    | `/hone`          |
| Reflect on my process                   | `/retro`               |
| Package an investigation for a teammate | `/rca`                 |
| Find a past session                     | `/index`               |
| Save a reference artifact mid-session   | `/persist`             |
| Persist with name and tags              | `/persist <name> <tag1> <tag2>...` |
| Find sessions by topic                  | `/index <filter>`      |
| Search inside archived artifacts        | `/index --deep <term>` |
| Archive scattered artifacts             | `/park --archive-system`           |
| Preview archive cleanup                | `/park --archive-system --dry-run` |
| Archive everything non-interactively   | `/park --archive-system --all`     |
