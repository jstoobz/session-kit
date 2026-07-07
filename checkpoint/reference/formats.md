# Checkpoint — Artifact Formats

The body template for `CHECKPOINT_CONTEXT.md`. Load this file when composing
`$CHECKPOINT_BODY` (Process step 4 of [../SKILL.md](../SKILL.md)).

## CHECKPOINT_CONTEXT.md format

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

**Skip empty sections.** If there are no decisions, no dead ends, no open items — omit
those sections entirely.
