---
name: index
description: Scan $SESSION_KIT_ROOT/manifest.json (default ~/.stoobz/) for session artifacts and build a searchable index of past work. Use when the user says "/index", "find that session", "list my sessions", "what did I work on", "where was that investigation", or needs to locate a past session by topic or ticket. Supports filtering by tag, project, summary, label, or branch. Use --deep to search inside artifact content. Falls back to filesystem scan if no manifest exists.
---

# Index

Find and catalog past sessions from the manifest (and surface unregistered active dirs as orphans).

> **Archive root:** `$SESSION_KIT_ROOT` (default `~/.stoobz`). The `sk` binary resolves it automatically; this skill just hands `$@` through.

## Process

Compose nothing. `/index` is a query, not an artifact. Pass the operator's args straight through to the `sk index` subcommand and surface its stdout to the user:

```bash
sk index "$@"
```

That's the entire skill body. The binary handles filtering, rendering, JSON output, the orphans filesystem scan, and the deep-content grep. Run `sk index --help` for the authoritative argument reference.

## Arguments

| Flag / arg | Effect |
|------------|--------|
| `<filter>` | Positional substring (case-insensitive) matched against `tags`, `summary`, `label`, `project`, `branch`, `session_id`, `chain_id`, and the `last_exchange` text |
| `--active` | Only sessions with `status: "active"` (renders an Active Sessions table; archived section suppressed) |
| `--orphans` | Filesystem scan for `<sid>-active/` directories with no manifest entry (legacy / un-checked-in sessions) — read side of the WAL pattern from ADR-0004 |
| `--chain` | Group sessions by `chain_id`, sorted by `chain_position`; shows fork annotations for `/checkpoint` branches |
| `--since <when>` | Date filter: `today`, `week`, `month`, or `YYYY-MM-DD` |
| `--deep <pattern>` | Grep through archived artifact text for `pattern` (case-insensitive) |
| `--json` | Structured JSON output (active + archived + orphans + deep hits) |
| `--debug` | Stderr trace of counts for each section |

Filters combine: `sk index --active foo` shows only active sessions whose haystack contains `foo`. `--chain <term>` filters chains by `chain_id`, `project`, or `summary`, and also surfaces chains forked from a matched chain.

## Scope note: `--orphans`

`--orphans` covers the **filesystem-without-manifest** direction only — `<sid>-active/` directories that were created by something other than `sk checkin` (legacy or hand-built fixtures). The inverse — manifest entries with `status: "active"` whose work has stalled — is a different concern (ADR-0007, abandoned-but-registered) and not handled here.

## Examples

```
/index                         → all archived sessions, newest first
/index auth                    → filter by tags/summary/label/project/branch
/index --active                → only in-flight sessions
/index --orphans               → filesystem dirs that never registered
/index --chain                 → grouped by chain, with fork annotations
/index --chain brrp-migration  → one chain + its branches
/index --since week            → last 7 days
/index --since 2026-04-01      → on or after that date
/index --deep "rate limit"     → grep archived artifact bodies
/index --json                  → structured payload
```

## Output legend

The default archived table includes an `Artifacts` column with single-letter badges:

| Letter | Artifact |
|--------|----------|
| `T` | TLDR.md |
| `C` | CONTEXT_FOR_NEXT_SESSION.md |
| `K` | CHECKPOINT_CONTEXT.md |
| `R` | RETRO.md |
| `P` | HONE.md |
| `H` | HANDOFF.md |
| `I` | INVESTIGATION_SUMMARY.md / INVESTIGATION_CONTEXT.md |

Active sessions render with `Since` / `Last Active` / `Branch` / `Last Exchange` / `Resume` columns so the operator can `cd` and `--resume` the session directly.

## Exit codes

`sk index` returns:

| Code | Meaning |
|------|---------|
| `0` | Success (including empty result sets) |
| `3` | Usage error (bad `--since` value) |

## Rules

- **One invocation, no composition.** Don't pre-process args; pass them through verbatim.
- **Manifest is truth.** When the manifest exists, the binary trusts it. The filesystem scan only fires for `--orphans`.
- **Present, don't write.** `/index` produces no artifact. Render the subcommand output as-is.
- **Suggest `/pickup` where it makes sense.** If an Active row's `Resume` command points at a different cwd, mention "Has resume context — `cd` there and `/pickup`."

## See also

- [checkin/SKILL.md](../checkin/SKILL.md) — the registration side of the WAL pattern
- `sk index --help` — authoritative arg reference
- [ADR-0004](~/.stoobz/kb/adr/0004-session-kit-artifact-durability.md), [ADR-0005](~/.stoobz/kb/adr/0005-skills-as-thin-orchestrators-of-versioned-scripts.md)
