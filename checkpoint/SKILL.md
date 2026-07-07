---
name: checkpoint
description: Synthesize context from selected chain nodes into a focused starting point. Use when the user says "/checkpoint", "synthesize these sessions", "branch from chain", "cherry-pick sessions", or wants to combine findings from specific past sessions while leaving dead ends behind. Reads archived artifacts from selected chain nodes, synthesizes a focused context, and writes a relay baton that starts a new branch chain. The pruned context becomes a clean starting point.
---

# Checkpoint

Selective synthesis across chain nodes. Turns a linear chain into a DAG — carry what matters, leave behind what doesn't.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Check-In (precondition)

The artifact writes below run through `sk write-artifact`, which invokes `sk checkin --silent --invoking checkpoint` in-process — no separate check-in step is needed. If a write exits `1` (durability failure, including the checkin precondition), abort: do not claim the checkpoint happened. See [checkin/SKILL.md](../checkin/SKILL.md) for the registration protocol.

## How It Fits

```
/relay      → "carry THIS session forward"     (linear, 1:1)
/checkpoint → "synthesize THESE nodes, branch"  (selective, N:1, creates DAG)
/pickup     → reads either one the same way     (no change needed)
```

Checkpoint writes to `CONTEXT_FOR_NEXT_SESSION.md` (the relay baton) — `/pickup` already knows how to consume it. The only extension is additional metadata in the `<!-- session-kit-chain -->` block.

## Invocation

```
/checkpoint                      → synthesize ALL nodes in current chain
/checkpoint 1,2,4                → specific nodes by chain_position
/checkpoint --exclude 3          → all except specified
/checkpoint --chain brrp 1,2,4   → explicit chain + nodes
/checkpoint --label focused-fix  → custom name for the new branch chain
```

**Current chain detection:** Look up the active manifest entry for this session (by `session_id`). Read its `chain_id`. If no active entry or no chain_id, ask: "Which chain? Use `/index --chain` to find one."

## Process

### 1. Resolve chain and nodes

1. **Detect chain** — Find the current chain from manifest (active entry's `chain_id`), or use `--chain <id>` if specified.
2. **Query manifest** for all entries with matching `chain_id`, sorted by `chain_position`.
3. **Apply node selection:**
   - No args → all nodes
   - `1,2,4` → only those positions
   - `--exclude 3` → all minus specified
4. **Validate:** at least 1 node selected, all requested positions exist. Error clearly if not:
   - "Chain `{id}` has {N} nodes (positions 1-{N}). Position {X} doesn't exist."
   - "No chain found. Use `/index --chain` to find one, or specify with `--chain <id>`."

### 2. Read archived artifacts from each selected node

For each node, read from its `archive_path` (under `~/.stoobz/`):

**Priority order per node** (read what exists, skip what doesn't):
1. `CONTEXT_FOR_NEXT_SESSION.md` — operational context, decisions, next steps
2. `TLDR.md` — summary of findings, changes, open items
3. `INVESTIGATION_SUMMARY.md` / `INVESTIGATION_CONTEXT.md` — investigation artifacts
4. `HONE.md` — original prompt + optimized version (useful for understanding intent)
5. Any persisted reference artifacts (`*.md` that isn't one of the above)

**Don't read:** `RETRO.md` (process reflection, not operational context), `HANDOFF.md` (teammate-facing, overlaps with TLDR).

### 3. Synthesize

This is the core value — not concatenation but analysis-informed synthesis:

1. **Thread identification:** What themes, goals, or investigations span the selected nodes?
2. **Decision accumulation:** Collect all decisions made across nodes. Note which are still valid vs. superseded.
3. **Finding consolidation:** Merge findings, removing duplicates. Flag contradictions.
4. **Dead-end pruning:** If excluded nodes contained approaches that were abandoned, note them briefly as "tried and ruled out" (so the next session doesn't repeat them).
5. **Open items merge:** Collect open items from all nodes. Check off any that were resolved in later nodes. Carry forward remaining.
6. **File/path deduplication:** Consolidate key files referenced across nodes into one list.

### 4. Write CHECKPOINT_CONTEXT.md

Compose `$CHECKPOINT_BODY` in the format below, then write it through the substrate — one call performs the durable-first ordering (archive → verify → ledger append → cwd mirror; see [write-artifact-protocol.md](../write-artifact-protocol.md)). A checkpoint synthesis is effectively irreproducible — the same nodes would produce a similar but never identical synthesis — so the durable copy matters more than usual:

```bash
sk write-artifact --skill checkpoint --artifact CHECKPOINT_CONTEXT.md --content-stdin <<< "$CHECKPOINT_BODY"
```

The body template lives in [reference/formats.md](reference/formats.md) — load it when
composing `$CHECKPOINT_BODY`. Skip empty sections (no decisions, no dead ends, no open
items → omit those sections entirely).

### 5. Write relay baton (CONTEXT_FOR_NEXT_SESSION.md)

Use the standard relay format (from `/relay`), but sourced from the checkpoint synthesis instead of the current session, and include the extended chain metadata block below **in the body**. (Unlike `/park`, where `sk park-finalize` appends the block after the fact, `/checkpoint` writes it inline — it describes the *new branch chain*, and `/pickup`'s `--inherit-chain-from` parses the first block in the file, so the branch identity wins even after a later `/park` appends this session's own block.)

```bash
sk write-artifact --skill checkpoint --artifact CONTEXT_FOR_NEXT_SESSION.md --content-stdin <<< "$BATON_BODY"
```

The chain metadata block:

```markdown
<!-- session-kit-chain
chain_id: {new-chain-id}
session_id: {current session's uuid}
chain_position: 1
parent_chain_id: {source chain_id}
checkpoint_nodes: 1,2,4
-->
```

**New chain naming:**
- Default: `{source-chain-id}-cp-{YYYY-MM-DD}` (e.g., `brrp-migration-cp-2026-03-01`)
- With `--label`: use the label directly (e.g., `--label focused-fix` → chain_id = `focused-fix`)

### 6. Manifest — known substrate gap

No new session entry — check-in already registered this session. The original design also stamped `parent_chain_id` / `checkpoint_nodes` onto the *current* session's active manifest entry, but the substrate has no write path for chain fields after first-checkin (`sk checkin`'s chain flags are first-checkin-only; `sk park-finalize` has no flags for them). **Do not hand-edit `manifest.json` to compensate** — leave the gap visible rather than faking a write path the system doesn't have.

What still works without it: the branch metadata reaches the *next* session regardless — `/pickup` inherits `parent_chain_id` / `checkpoint_nodes` from the baton's chain block, so the branch and its fork annotation appear in `/index --chain` from the first picked-up node onward. The only loss is branch metadata on the checkpoint-*creating* session's own archived entry. Closing it properly is a scoped substrate follow-up (a chain-field update path on `sk`, e.g. flags on `park-finalize`).

### 7. Confirm

```
Checkpoint synthesized from chain "{chain_id}".

  Nodes:     1, 2, 4 (of 4 total, excluded: 3)
  Archived:  <active-archive>/CHECKPOINT_CONTEXT.md   (path printed by sk write-artifact)
  Local:     .stoobz/CHECKPOINT_CONTEXT.md
  Relay:     .stoobz/CONTEXT_FOR_NEXT_SESSION.md (ready for /pickup)
  New chain: {new-chain-id} (branched from {source-chain-id})

  /pickup in a new session to start from this checkpoint.
  /index --chain to see the branch in context.
```

"Archived" listed first intentionally — the archive is the durable copy, written first.

## Rules

- **Synthesize, don't concatenate** — The core value is analytical judgment: threading themes, resolving contradictions, pruning dead ends. Don't just paste artifacts together.
- **Write through the substrate** — both artifacts go via `sk write-artifact` (durable-first ordering handled there; see [write-artifact-protocol.md](../write-artifact-protocol.md)). Never hand-write into the archive tree or hand-edit the manifest.
- **Skip empty sections** — Don't include empty Tried and Ruled Out, Decisions, or Open Items sections.
- **Respect RETRO/HANDOFF exclusion** — RETRO is process reflection, HANDOFF overlaps with TLDR. Neither carries operational context.
- **Error early on bad input** — If chain doesn't exist or positions are invalid, say so immediately with actionable guidance.
- **Preserve traceability** — The Source Artifacts table links every node to its archive. This is how someone traces a finding back to its origin.
- **Don't overwrite existing checkpoints** — If `.stoobz/CHECKPOINT_CONTEXT.md` exists, preserve it under a `## Previous Checkpoint` heading (same pattern as other session-kit artifacts).
- **Manifest is append-only** — Never remove entries; field updates happen only through `sk` subcommands.

## Exit Codes

`sk write-artifact` returns per-call:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Durable write + mirror both succeeded | Continue |
| `1` | Durability failure (archive, verify, ledger, or precondition checkin) | Abort; do not claim the checkpoint happened |
| `2` | Durable write succeeded; cwd mirror failed | Mention the warning; archive is authoritative |
| `3` | Usage error | Fix invocation |

## See also

- [reference/formats.md](reference/formats.md) — the CHECKPOINT_CONTEXT.md body template
- [relay/SKILL.md](../relay/SKILL.md) — the baton format this skill reuses
- [pickup/SKILL.md](../pickup/SKILL.md) — how the baton's chain block is inherited next session
- [checkin/SKILL.md](../checkin/SKILL.md), [write-artifact-protocol.md](../write-artifact-protocol.md)
- `sk write-artifact --help`
