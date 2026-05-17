# Session Kit

A composable set of Claude Code skills for managing session lifecycle — from starting work, through the session, to parking it and sharing results.

Skills in this kit are **thin orchestrators** over a single Python CLI (`sk`). SKILL.md owns the contract (what / when / why) and any Claude-judgment composition (drafting an artifact body, inferring a label); deterministic plumbing (session-id resolution, manifest read-modify-write, ledger append, durable-first write, chain inheritance, archive finalization, manifest queries) lives in the `sk` binary. See [ADR-0005](https://github.com/jstoobz/dotfiles/blob/main/.stoobz/kb/adr/0005-skills-as-thin-orchestrators-of-versioned-scripts.md).

## Architecture

```
session-kit/
├── bin/
│   └── sk                    # uv-managed entrypoint (PEP 723 inline deps)
├── session_kit/              # Python package (Typer subcommands)
│   ├── __main__.py           # registers checkin, write-artifact, park-finalize, index
│   ├── common.py             # SESSION_KIT_ROOT, session-id resolver, atomic-JSON-RMW
│   ├── checkin.py            # registration + scaffolding + liveness refresh
│   ├── write_artifact.py     # durable-first write + ledger append + cwd mirror + tag merge
│   ├── park_finalize.py      # active → archived rename + manifest flip + chain block
│   ├── index.py              # manifest queries + orphan scan + deep grep
│   └── tests/                # pytest unit tests
├── {skill}/SKILL.md          # 13 thin orchestrators
├── link.sh                   # symlinks skills into ~/.claude/skills/ + sk into ~/.local/bin/
├── session-kit.md            # this file
├── guide.md                  # workflow walkthrough
└── README.md                 # public quick start
```

`link.sh` installs `bin/sk` at `~/.local/bin/sk`. Requires `uv` on `PATH` (the `sk` shebang is `#!/usr/bin/env -S uv run --quiet --script`; dependencies — `typer`, `filelock` — are declared inline via PEP 723).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SESSION_KIT_ROOT` | `~/.stoobz` | Root directory for archives and manifest |

`SESSION_KIT_*` is the operator-facing prefix (set in your shell init). Internal plumbing uses `SK_*` env vars; operators rarely touch those. All `~/.stoobz/` paths in this document refer to the resolved root.

## Skills

### Registration

| Command | Purpose |
|---------|---------|
| `/checkin` | Register the current Claude Code session — creates the active manifest entry + pre-allocates `<sid>-active/` and the empty ledger. Every artifact-writing skill calls `sk checkin --silent` first. |

### Core Artifacts

| Command       | Output                                                              | Purpose                                                                                                                                                                        |
| ------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/tldr`       | `.stoobz/TLDR.md`                                                   | Concise session summary for sharing with engineers. Key findings, decisions, changes, open items. 2-minute read max.                                                           |
| `/relay`      | `.stoobz/CONTEXT_FOR_NEXT_SESSION.md`                               | Everything Claude needs to resume in a new session. Paths, branch state, decisions, next steps.                                                                                |
| `/checkpoint` | `.stoobz/CHECKPOINT_CONTEXT.md`, `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` | Selective synthesis across chain nodes. Synthesizes a focused context and writes a relay baton that starts a new branch chain.                                              |
| `/hone`       | `.stoobz/HONE.md`                                                   | Captures your original prompt verbatim, analyzes it, generates an optimized version, and provides coaching tips.                                                              |
| `/retro`      | `.stoobz/RETRO.md`                                                  | Session retrospective — what went well, what took longer than expected, what to do differently.                                                                                |
| `/handoff`    | `.stoobz/HANDOFF.md`                                                | Teammate-facing write-up with full business context, evidence, recommendations.                                                                                                |
| `/rca`        | `.stoobz/INVESTIGATION_SUMMARY.md`, `.stoobz/INVESTIGATION_CONTEXT.md`, `.stoobz/evidence/` | Root cause analysis package — quick-scan + Claude-droppable deep context + raw evidence.                                              |

### Project Setup

| Command            | Output                                                       | Purpose                                                                                            |
| ------------------ | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `/prime`           | `.claude/skills/*/SKILL.md`, `.claude/commands/contexts/*.md` | Analyzes codebase, creates expert skills + feature/debug context files for all future sessions.    |
| `/prime --refresh` | _(updates existing skills)_                                  | Checks staleness, re-analyzes changed layers, updates skills surgically.                            |

### Lifecycle

| Command                  | Output                                                            | Purpose                                                                                                                        |
| ------------------------ | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `/park`                  | TLDR + relay + HONE, archived                                     | End session: generate artifacts, `sk park-finalize` flips manifest to archived, relay baton stays in `./.stoobz/`.            |
| `/park <label>`          | _(same as /park)_                                                  | Park with explicit label (e.g., `/park PROJ-1234`).                                                                            |
| `/park --archive-system` | _(scans and archives)_                                             | Retroactive cleanup — finds scattered `.stoobz/` dirs and loose artifacts. Currently the pre-2C prose stub; see `park/SKILL.md`. |
| `/persist <name> <tags>` | `<name>.md` in `./.stoobz/`                                       | Save a reference artifact mid-session. Tags merge-dedupe into the manifest entry's `tags[]` via `sk write-artifact --tags`.    |
| `/pickup`                | _(reads existing artifacts)_                                       | Loads prior session context, presents a briefing, inherits chain metadata via `sk checkin --inherit-chain-from`.               |
| `/index`                 | _(displayed)_                                                      | Archived sessions, newest first. `sk index` handles filter / chain / since / deep / json / orphans.                            |
| `/index <filter>`        | _(displayed)_                                                      | Substring search across tags / summary / label / project / branch / session_id / chain_id / last_exchange.                     |
| `/index --active`        | _(displayed)_                                                      | In-flight sessions with resume commands.                                                                                       |
| `/index --orphans`       | _(displayed)_                                                      | Filesystem `<sid>-active/` dirs not in the manifest (legacy recovery).                                                         |
| `/index --chain [term]`  | _(displayed)_                                                      | Group by chain, show fork annotations.                                                                                          |
| `/index --since <when>`  | _(displayed)_                                                      | `today` / `week` / `month` / `YYYY-MM-DD`.                                                                                      |
| `/index --deep <term>`   | _(displayed)_                                                      | Grep inside archived artifact bodies.                                                                                           |
| `/checkpoint`            | `CHECKPOINT_CONTEXT.md`, `CONTEXT_FOR_NEXT_SESSION.md`             | Synthesize selected chain nodes into a focused starting point. Creates a branch chain.                                          |
| `/sweep`                 | _(interactive)_                                                    | Cleanup of old Claude Code sessions from the resume picker.                                                                     |

## Session Check-In (WAL-style registration)

Session Kit registers an "active" manifest entry *before* the first durable artifact write, so any reader (`/index`, sibling sessions) sees in-flight work without waiting for `/park`. This is the [write-ahead log](https://en.wikipedia.org/wiki/Write-ahead_logging) pattern applied to artifacts:

1. **First skill invocation** → `sk checkin --silent --invoking <skill>` registers the session: detects the JSONL session UUID (with git-root / synthesized-UUID fallbacks), creates the `status: active` manifest entry, pre-allocates `<sid>-active/`, and writes the empty `.session-artifacts.json` ledger.
2. **Each artifact write** → `sk write-artifact` calls checkin in-process, durably writes to the active dir, appends a ledger row, mirrors to `cwd/.stoobz/`, and (optionally) merges `--tags` into the manifest entry's `tags[]`.
3. **`/park`** → `sk park-finalize` reads the ledger as the authoritative artifact list, renames `<sid>-active/` → `<date>-<label>/`, flips `status` → `archived`, populates `id`/`label`/`summary`/`archive_path`, appends the chain block to the relay baton.
4. **Crash recovery** → `<sid>-active/` dirs that never archived show up under `/index --orphans`.

See [checkin/SKILL.md](checkin/SKILL.md) for the full contract including session-ID detection, chain inheritance, and graceful degradation.

### Session Chains

A **chain** is a logical work stream spanning multiple Claude Code sessions:

- `/park` writes a `<!-- session-kit-chain ... -->` block at the bottom of `CONTEXT_FOR_NEXT_SESSION.md`.
- `/pickup` runs `sk checkin --inherit-chain-from <baton-path>`. The binary parses the chain block, sets the new manifest entry's `chain_id`, `previous_session_id`, `chain_position = parent + 1`, `parent_chain_id`, `checkpoint_nodes`. Write-once at first checkin; preserved on re-entry.
- `/checkpoint` synthesizes selected nodes from a chain and branches into a new chain (linked list → DAG).
- `/index --chain` groups sessions by chain with fork annotations for checkpoint branches.
- Chains can span projects — `chain_id` is the thread, `project` varies per node.

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
                                              updated       Full write-up               Archives via sk park-finalize:
                              CHECK-IN                      for teammates                 ~/.stoobz/sessions/<project>/<date>/
                                ↓                                                       Relay baton stays in .stoobz/
                              Manifest       /persist (anytime)                          Chain metadata in relay baton
                              updated          Save a reference              CHECK-IN    status: active → archived
                                               artifact mid-session           ↓
                                               → .stoobz/<name>.md         Manifest      /retro (optional)
                                               Tags merge into             updated         Process reflection
                                               manifest tags[]
Later                         Branch
  |                             |
  v                             v
/index                      /checkpoint
  sk index (manifest read)    Synthesize N chain nodes
  Filter by tag/project       Prune dead ends
  --active: live sessions     Write focused relay baton
  --orphans: unregistered     Branch chain (creates DAG)
  --since: time filter        /pickup to start from checkpoint
  --chain: work streams
  --deep: grep archived text
```

## Composability Flows

### New Repo Onboarding

```
First session:  /prime → creates expert skills + contexts
Every session:  /pickup → [work with expert skills loaded] → /park
Months later:   /prime --refresh → updates skills for architecture changes
```

### Solo Deep Dive

```
Session 1:  [do work] → /park
Session 2:  /pickup → [continue] → /park
Session 3:  /pickup → [wrap up] → /park + /retro
```

### Sharing with Team

```
[complete investigation] → /tldr      (quick share in Slack)
                         → /handoff   (full context for PR review or pairing)
                         → /rca       (investigation package — teammate + their Claude pick it up)
```

### Production Investigation

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

### Finding Past Work

```
/index                          → all sessions from manifest
/index elixir                   → filter by tag
/index memory leak              → filter by summary/label
/index --active                 → in-flight sessions with resume commands
/index --orphans                → recover legacy unregistered dirs
/index --deep "rate limit"      → grep archived artifact text
cd into source_dir → /pickup    → resume that work
```

## File Existence Behavior

All artifact-generating skills check for existing files in `./.stoobz/` before writing:

- If the file exists, previous content is preserved under a timestamped "Previous" heading
- New content is added as the primary (top) section
- This creates a rolling history — latest first, older entries below
- Open items from previous sessions are carried forward (completed items checked off)

## Durable-First Principle

`sk write-artifact` writes to the durable archive (`<sid>-active/`) first, then mirrors to `cwd/.stoobz/`. If only one write succeeds, it is the durable one. The ledger records every write so `/park` finalizes from an authoritative list instead of a hard-coded allowlist.

| Skill | Calls `sk write-artifact` | Notes |
|-------|--------------------------|-------|
| `/tldr`, `/relay`, `/hone`, `/retro`, `/handoff`, `/persist` | Yes | One call per artifact |
| `/rca` | Yes | One call per file (SUMMARY, CONTEXT, every evidence file) |
| `/park` | Yes | Three calls for TLDR/RELAY/HONE, then `sk park-finalize` |
| `/checkpoint` | Yes | Writes baton + CHECKPOINT_CONTEXT.md |

See [write-artifact-protocol.md](write-artifact-protocol.md) and [ADR-0004](https://github.com/jstoobz/dotfiles/blob/main/.stoobz/kb/adr/0004-session-kit-artifact-durability.md).

## Archive Convention

```
~/.stoobz/
├── manifest.json                                ← fast index for /index
└── sessions/
    ├── my-project/
    │   ├── <sid>-active/                        ← live session (created by sk checkin)
    │   │   ├── .session-artifacts.json          ← ledger
    │   │   └── (in-flight artifacts)
    │   ├── 2026-02-13-PROJ-1234/                ← /park renamed it
    │   │   ├── .session-artifacts.json
    │   │   ├── TLDR.md
    │   │   ├── HONE.md
    │   │   └── RETRO.md
    │   └── auth-flow-notes.md                   ← /persist reference artifact
    └── api-gateway/
        └── 2026-01-28-rate-limiting/
            ├── TLDR.md
            └── INVESTIGATION_SUMMARY.md
```

- `CONTEXT_FOR_NEXT_SESSION.md` stays in `./.stoobz/` after `/park` (relay baton for `/pickup`).
- `manifest.json` is the single source of truth for `/index`. Active entries are visible while in-flight thanks to `sk checkin`.
- Sessions with `chain_id` form chains visible via `/index --chain`.
- `<sid>-active/` dirs without a matching manifest entry are surfaced by `/index --orphans`.

## Quick Reference

| I want to...                            | Use                                |
| --------------------------------------- | ---------------------------------- |
| Set up expert skills for a new repo     | `/prime`                           |
| Update stale expert skills              | `/prime --refresh`                 |
| Save everything before stepping away    | `/park`                            |
| Park with a specific label              | `/park <label>`                    |
| Resume where I left off                 | `/pickup`                          |
| Share a quick summary                   | `/tldr`                            |
| Write up findings for the team          | `/handoff`                         |
| Save context for my next session        | `/relay`                           |
| Improve my prompting                    | `/hone`                            |
| Reflect on my process                   | `/retro`                           |
| Package an investigation for a teammate | `/rca`                             |
| Find a past session                     | `/index`                           |
| Save a reference artifact mid-session   | `/persist`                         |
| Persist with name and tags              | `/persist <name> <tag1> <tag2>...` |
| Find sessions by topic                  | `/index <filter>`                  |
| Search inside archived artifacts        | `/index --deep <term>`             |
| Find active sessions                    | `/index --active`                  |
| Recover unregistered active dirs        | `/index --orphans`                 |
| Find recent work                        | `/index --since week`              |
| View a work stream timeline             | `/index --chain <term>`            |
| Synthesize selected sessions            | `/checkpoint`                      |
| Checkpoint specific nodes               | `/checkpoint 1,2,4`                |
| Resume a crashed session                | Copy `return_to` from `/index --active` |
