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
| `/tldr`       | `.stoobz/TLDR.md`                                                           | Concise session summary for sharing with engineers. Key findings, decisions, changes, open items. 2-minute read max.                                                           |
| `/relay`      | `.stoobz/CONTEXT_FOR_NEXT_SESSION.md`                                       | Everything Claude needs to resume in a new session. Optimized for machine consumption — paths, branch state, decisions, next steps, auto-detected skills to load.                            |
| `/checkpoint` | `.stoobz/CHECKPOINT_CONTEXT.md`, `.stoobz/CONTEXT_FOR_NEXT_SESSION.md`      | Selective synthesis across chain nodes. Reads archived artifacts from selected sessions, synthesizes a focused context, and writes a relay baton that starts a new branch chain. |
| `/hone` | `.stoobz/HONE.md`                                                     | Captures your original prompt verbatim, analyzes its effectiveness, generates an optimized version, and provides coaching tips. Builds prompt engineering intuition over time. |
| `/retro`      | `.stoobz/RETRO.md`                                                          | Session retrospective — what went well, what took longer than expected, what to do differently. Tracks recurring patterns across sessions.                                     |
| `/handoff`    | `.stoobz/HANDOFF.md`                                                        | Teammate-facing write-up with full business context, evidence, recommendations, and links. No Claude artifacts — pure human-to-human communication.                            |
| `/rca`        | `.stoobz/INVESTIGATION_SUMMARY.md`, `.stoobz/INVESTIGATION_CONTEXT.md`, `.stoobz/evidence/` | Root cause analysis package — quick-scan summary + Claude-droppable deep context + raw evidence. Designed for engineer + Claude consumption without any skill setup.           |

### Project Setup

| Command                | Output                                                            | Purpose                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `/prime`                 | `.claude/skills/*/SKILL.md`, `.claude/commands/contexts/*.md`       | "Set up this repo." Analyzes codebase architecture, creates expert skills + feature/debug context files for all future sessions. |
| `/prime --refresh`       | _(updates existing skills)_                                        | "Things changed." Checks staleness, re-analyzes changed layers, updates skills surgically.                                      |

### Lifecycle Commands

| Command                | Output                                                            | Purpose                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `/park`                  | `.stoobz/TLDR.md`, `.stoobz/CONTEXT_FOR_NEXT_SESSION.md`, `.stoobz/HONE.md`          | "I'm stepping away." Generates all core artifacts in `./.stoobz/`, archives to `~/.stoobz/sessions/<project>/<date-label>/`. Relay baton stays in `./.stoobz/`. |
| `/park <label>`          | _(same as /park)_                                                  | Park with an explicit label for the archive directory (e.g., `/park PROJ-1234`).                                               |
| `/park --archive-system` | _(scans and archives)_                                             | Retroactive cleanup — finds scattered `.stoobz/` dirs and loose artifacts, archives full subtrees to `~/.stoobz/sessions/`. Flags: `--select` (default), `--all`, `--dry-run`, `--clean`. |
| `/retro`                 | `RETRO.md`                                                         | Session retrospective — what went well, what took longer, what to do differently. Can run anytime; `/park` archives it if present. |
| `/persist`               | `<name>.md` in `./.stoobz/`                              | "Save this thing." Persists a reference artifact mid-session. Archived to `~/.stoobz/sessions/` when you `/park`.                                 |
| `/persist <name> <tags>` | `<name>.md` in `./.stoobz/`                              | Persist with explicit name and tags: `/persist runbook playbook deployment`.                                                    |
| `/pickup`                | _(reads existing artifacts)_                                       | "I'm back." Loads prior session context and presents a briefing. The complement to `/park`.                                    |
| `/index`                 | _(displayed, not written)_                                         | "Where was that?" Reads `~/.stoobz/manifest.json` for fast lookup. Supports filtering by topic, tag, or project.              |
| `/index <filter>`        | _(displayed, not written)_                                         | Filter sessions — searches tags, summary, label, project, and branch (case-insensitive).                                      |
| `/index --deep <term>`   | _(displayed, not written)_                                         | Deep search — greps inside archived artifact content when manifest metadata isn't enough.                                      |
| `/checkpoint`            | `.stoobz/CHECKPOINT_CONTEXT.md`, `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` | Synthesize selected chain nodes into a focused starting point. Creates a branch chain. |
| `/checkpoint 1,2,4`     | _(same as /checkpoint)_                                            | Checkpoint specific nodes by chain position.                                                                                    |
| `/checkpoint --exclude 3`| _(same as /checkpoint)_                                           | Checkpoint all nodes except specified.                                                                                          |

## Session Check-In

Session Kit registers active sessions in the manifest on first skill use. This makes live sessions discoverable via `/index --active` even if the terminal crashes before `/park`.

- First skill invocation → detects Claude Code session UUID → creates `"active"` manifest entry
- Subsequent skill invocations → updates `last_activity` and `last_exchange`
- `/park` → upgrades entry to `"archived"` with full metadata
- Entries without `status` field → treated as `"archived"` (backward compatible)

See [session-checkin.md](session-checkin.md) for the full protocol including session ID detection, chain propagation, and graceful degradation.

### Session Chains

A **chain** is a logical work stream spanning multiple Claude Code sessions connected via park/pickup. Chains enable tracking related sessions across projects and time:

- `/park` writes chain metadata into the relay baton (`CONTEXT_FOR_NEXT_SESSION.md`)
- `/pickup` inherits chain identity from the relay baton, incrementing position
- `/checkpoint` synthesizes selected nodes from a chain and branches into a new chain (turning the linked list into a DAG)
- `/index --chain` groups sessions by chain for a full work stream timeline, with fork annotations for checkpoint branches
- Chains can span projects (e.g., stoobz-api → stoobz-web) — `chain_id` is the thread, `project` varies per node

## Session Lifecycle

```
Setup                         Start                         During                        End
  |                             |                             |                            |
  v                             v                             v                            v
/prime                      /pickup                    /tldr (anytime)              /park
  Analyze codebase            Read .stoobz/               Quick summary               Generates in .stoobz/:
  Create expert skills        Load skills     CHECK-IN      for sharing                   TLDR.md
  Create contexts             Present briefing  ↓                                         CONTEXT_FOR_NEXT_SESSION.md
  (run once or --refresh)     Inherit chain   Manifest    /handoff (anytime)                HONE.md
                                              updated       Full write-up               Archives to:
                              CHECK-IN                      for teammates                 ~/.stoobz/sessions/<project>/<date>/
                                ↓                                                       Relay baton stays in .stoobz/
                              Manifest       /persist (anytime)                          Chain metadata in relay baton
                              updated          Save a reference              CHECK-IN    Updates manifest.json
                                               artifact mid-session           ↓          Active → Archived
                                               → .stoobz/<name>.md         Manifest
                                                                            updated    /retro (optional)
                                                                                         Process reflection
Later                         Branch
  |                             |
  v                             v
/index                      /checkpoint
  Fast manifest lookup        Synthesize N chain nodes
  Filter by tag/project       Prune dead ends
  --active: live sessions     Write focused relay baton
  --since: time filter        Branch chain (creates DAG)
  --chain: work streams       /pickup to start from checkpoint
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

### Chain Branching (selective synthesis)

```
Session 1:  [investigate approach A] → /park
Session 2:  /pickup → [investigate approach B, dead end] → /park
Session 3:  /pickup → [investigate approach C] → /park
Session 4:  /checkpoint 1,3 → synthesize sessions 1+3, skip the dead end
New session: /pickup → start from clean checkpoint (approach A+C context only)
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

All artifact-generating skills check for existing files in `./.stoobz/` before writing:

- If the file exists, previous content is preserved under a timestamped "Previous" heading
- New content is added as the primary (top) section
- This creates a rolling history — latest first, older entries below
- Open items from previous sessions are carried forward (completed items checked off)

## Archive-First Principle

**Write to the archive before writing to the local `.stoobz/` directory.** This applies to every skill that writes artifacts to both locations.

The archive (`~/.stoobz/sessions/`) is the durable, long-term store. The local `./.stoobz/` is the volatile working copy. If a crash happens between writes, the durable copy should be the one that survives.

| Skill | Follows archive-first | Why it matters |
|-------|----------------------|----------------|
| `/checkpoint` | Yes | Synthesis is irreproducible — analytical judgment varies with context |
| `/persist` | Yes | Reference artifacts are immediate-write to archive |
| `/park` | Not yet | Currently writes local first then archives — future refactor will align it |

**The pattern:** `mkdir -p` the archive path, write the file there, then copy to `./.stoobz/`. If only one write succeeds, it should be the durable one.

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

- `CONTEXT_FOR_NEXT_SESSION.md` is copied to the archive AND stays in `./.stoobz/` during normal `/park` (relay baton for `/pickup`). In `--archive-system` mode, it gets archived too (old sessions nobody is picking up).
- `CHECKPOINT_CONTEXT-<chain_id>.md` is written archive-first to `~/.stoobz/sessions/<project>/` alongside the checkpoint's relay baton (see [Archive-First Principle](#archive-first-principle)).
- `manifest.json` is the single source of truth for `/index`
- Archives are organized by project, then by date-label
- Sessions with `chain_id` form chains visible via `/index --chain`

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
| Find active sessions                    | `/index --active`      |
| Find recent work                        | `/index --since 1d`    |
| View a work stream timeline             | `/index --chain <term>` |
| Synthesize selected sessions            | `/checkpoint`          |
| Checkpoint specific nodes               | `/checkpoint 1,2,4`   |
| Checkpoint excluding nodes              | `/checkpoint --exclude 3` |
| Resume a crashed session                | Copy `return_to` from `/index --active` |
| Archive scattered artifacts             | `/park --archive-system`           |
| Preview archive cleanup                | `/park --archive-system --dry-run` |
| Archive everything non-interactively   | `/park --archive-system --all`     |
