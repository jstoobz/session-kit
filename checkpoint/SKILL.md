---
name: checkpoint
description: Synthesize context from selected chain nodes into a focused starting point. Use when the user says "/checkpoint", "synthesize these sessions", "branch from chain", "cherry-pick sessions", or wants to combine findings from specific past sessions while leaving dead ends behind. Reads archived artifacts from selected chain nodes, synthesizes a focused context, and writes a relay baton that starts a new branch chain. The pruned context becomes a clean starting point.
---

# Checkpoint

Selective synthesis across chain nodes. Turns a linear chain into a DAG — carry what matters, leave behind what doesn't.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Session Check-In (silent — before main process)

On first invocation of any session-kit skill in this session, register the active session in the manifest. See [session-checkin.md](../session-checkin.md) for the full protocol. Summary:

1. Detect session ID from most recently modified `.jsonl` in `~/.claude/projects/$(pwd | tr '/' '-')/` (fallback: git root encoding). If detection fails, skip silently.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create if missing).
3. If no entry with this `session_id` exists → create active registration (`status: "active"`, `session_id`, `return_to`, `started_at`, `last_activity`, `last_exchange`, `skills_used`, nulls for label/summary/archive_path).
4. If entry exists → update `last_activity`, `last_exchange`, append this skill to `skills_used`.
5. Write manifest. Proceed to main process. No output about check-in.

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

### 4. Write CHECKPOINT_CONTEXT.md (archive first)

**Archive first, always.** See [Archive-First Principle](#archive-first-principle) below. A checkpoint synthesis is effectively irreproducible — the same nodes would produce a similar but never identical synthesis because analytical judgment varies with context.

**Write order:**
1. `~/.stoobz/sessions/<project>/CHECKPOINT_CONTEXT-<chain_id>.md` (archive — durable)
2. `./.stoobz/CHECKPOINT_CONTEXT.md` (local — session convenience)

Both get identical content:

```markdown
# Checkpoint Context

**Date:** {YYYY-MM-DD}
**Source chain:** {chain_id} (nodes {selected} of {total})
**Pruned:** {excluded nodes with brief reason if inferable}

---

## Synthesized Goal

{The overarching goal across selected nodes — what we're trying to accomplish}

## Key Findings (across {N} sessions)

- {Consolidated finding — cite which node confirmed it}

## Decisions Still In Effect

| Decision | Made in | Rationale |
|----------|---------|-----------|
| {decision} | Node {N} | {why} |

## Tried and Ruled Out

{From excluded or superseded approaches — brief notes to prevent re-exploration}

- {Approach}: {why it was abandoned} (Node {N})

## Current State

{Where things stand after the selected nodes — what's built, what's confirmed, what's in progress}

## Key Files

- `{path}` — {role, which node(s) referenced it}

## Open Items

- [ ] {Carried forward from nodes, de-duped}

## Source Artifacts

{For traceability — link each node to its archive}

| Node | Date | Archive | Key Artifact |
|------|------|---------|-------------|
| 1 | {date} | {archive_path} | TLDR.md |
| 2 | {date} | {archive_path} | CONTEXT_FOR_NEXT_SESSION.md |
| 4 | {date} | {archive_path} | INVESTIGATION_SUMMARY.md |

---

_Checkpoint synthesized {date} from chain "{chain_id}" nodes {list}._
```

**Skip empty sections.** If there are no decisions, no dead ends, no open items — omit those sections entirely.

### 5. Write relay baton (CONTEXT_FOR_NEXT_SESSION.md)

Same archive-first pattern:
1. `~/.stoobz/sessions/<project>/CONTEXT_FOR_NEXT_SESSION.md` (alongside CHECKPOINT_CONTEXT.md)
2. `./.stoobz/CONTEXT_FOR_NEXT_SESSION.md` (local — the relay baton for `/pickup`)

Use the standard relay format (from `/relay`), but sourced from the checkpoint synthesis instead of the current session. Include an extended chain metadata block:

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

### 6. Update manifest

No new session entry — the check-in protocol already registered this session. Update the active entry to include:
- `parent_chain_id`: the source chain
- `checkpoint_nodes`: array of selected positions

These flow through to the archived entry when `/park` runs.

### 7. Confirm

```
Checkpoint synthesized from chain "{chain_id}".

  Nodes:     1, 2, 4 (of 4 total, excluded: 3)
  Archived:  ~/.stoobz/sessions/<project>/CHECKPOINT_CONTEXT-<chain_id>.md
  Local:     .stoobz/CHECKPOINT_CONTEXT.md
  Relay:     .stoobz/CONTEXT_FOR_NEXT_SESSION.md (ready for /pickup)
  New chain: {new-chain-id} (branched from {source-chain-id})

  /pickup in a new session to start from this checkpoint.
  /index --chain to see the branch in context.
```

"Archived" listed first intentionally — the archive is the durable copy, written first.

## Archive-First Principle

**Write to the archive before writing to the local `.stoobz/` directory.** This applies to every skill that writes artifacts to both locations.

The archive (`~/.stoobz/sessions/`) is the durable, long-term store. The local `./.stoobz/` is the volatile working copy. If a crash happens between writes, the durable copy should be the one that survives.

| Skill | Why archive-first matters |
|-------|--------------------------|
| `/checkpoint` | Synthesis is irreproducible — re-reading everything produces similar but never identical output |
| `/persist` | Reference artifacts are immediate-write to archive (already follows this) |
| `/park` | Currently writes local first then archives — should be reversed in a future pass |

**The pattern:** `mkdir -p` the archive path, write the file there, then copy to `./.stoobz/`. If only one write succeeds, it should be the durable one.

## Rules

- **Synthesize, don't concatenate** — The core value is analytical judgment: threading themes, resolving contradictions, pruning dead ends. Don't just paste artifacts together.
- **Archive first** — Always write to `~/.stoobz/sessions/` before `./.stoobz/`. If only one write succeeds, it should be the durable one.
- **Skip empty sections** — Don't include empty Tried and Ruled Out, Decisions, or Open Items sections.
- **Respect RETRO/HANDOFF exclusion** — RETRO is process reflection, HANDOFF overlaps with TLDR. Neither carries operational context.
- **Error early on bad input** — If chain doesn't exist or positions are invalid, say so immediately with actionable guidance.
- **Preserve traceability** — The Source Artifacts table links every node to its archive. This is how someone traces a finding back to its origin.
- **Don't overwrite existing checkpoints** — If `.stoobz/CHECKPOINT_CONTEXT.md` exists, preserve it under a `## Previous Checkpoint` heading (same pattern as other session-kit artifacts).
- **Manifest is append-only** — Never remove entries, only add or update fields.
