# Session Kit

A composable set of Claude Code skills for managing session lifecycle — from starting work, through the session, to parking it and sharing results.

Skills in this kit are **thin orchestrators** over a single Python CLI (`sk`). SKILL.md owns the contract (what / when / why) and any Claude-judgment composition (drafting an artifact body, inferring a label); deterministic plumbing (session-id resolution, manifest read-modify-write, ledger append, durable-first write, chain inheritance, archive finalization, manifest queries) lives in the `sk` binary.

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
├── {skill}/SKILL.md          # 14 skills: 13 sk-backed thin orchestrators + script-backed sweep
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

The skill catalog (registration, core artifacts, lifecycle, project setup, maintenance)
lives in [README.md](README.md#skills) — kept current there and only there. Workflow-level
composition patterns live in [guide.md](guide.md). This document stays on architecture:
the substrate, the protocols, and the data model.

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

See [write-artifact-protocol.md](write-artifact-protocol.md).

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
- **Archive dates are UTC**, not local time. A `/park` near midnight in a non-UTC timezone may produce a next-day-dated archive directory; grepping archives by date should account for the UTC boundary.
