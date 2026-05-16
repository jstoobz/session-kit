---
name: tldr
description: Generate a concise TLDR.md summary of the current session's key findings, decisions, and outcomes. Use when the user says "/tldr", "write a tldr", "summarize this session", "create a summary", or wants a shareable document capturing what happened in this conversation. Produces a clean, engineer-friendly markdown file ready to share before diving into full analysis.
---

# TLDR

Generate a `TLDR.md` file summarizing the current session for sharing with other engineers.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Check-In (precondition)

Before the Process section runs, invoke `/checkin` in **silent mode** as a precondition. See [checkin/SKILL.md](../checkin/SKILL.md) for the full protocol (three-tier session-ID resolution, active-dir + ledger creation, strict idempotency).

If `/checkin` aborts (mkdir or ledger creation failure — the only durability conditions that fail loudly), this skill aborts too. Do not proceed to the Process section. Do not write any artifact.

If `/checkin` succeeds or no-ops, proceed silently to the Process section. No output about check-in.

## Process

This skill writes its artifact under the **durable-first protocol**. See [write-artifact-protocol.md](../write-artifact-protocol.md) for the full contract; the abbreviated steps for `tldr` are below.

Let `ACTIVE_DIR = $SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/` (pre-allocated by check-in).

1. **Check for existing file at the canonical location** — Read `$ACTIVE_DIR/TLDR.md` if it exists (this is the durable copy; cwd is a mirror). If found:
   - Preserve previous content under a `## Previous Session` heading
   - Add new content as the primary (top) section with updated timestamp
   - This creates a rolling history — latest first

2. Review the full conversation to extract:
   - **What was investigated/built** — the problem or task
   - **Key findings** — discoveries, root causes, data points
   - **Decisions made** — choices and their rationale
   - **Actions taken** — code changes, config updates, commands run
   - **Open items** — unresolved questions, next steps, follow-ups

3. **Durable write** — Write the new content to `$ACTIVE_DIR/TLDR.md`. Then verify: the file exists and `size > 0`. If verification fails, treat this as a write failure; abort and surface the error.

4. **Append ledger entry** — Append to `$ACTIVE_DIR/.session-artifacts.json` under `artifacts`:
   ```json
   {
     "name": "TLDR.md",
     "written_at": "<iso8601-utc-now>",
     "skill": "tldr",
     "size_bytes": <bytes-written>
   }
   ```
   This append is the system-of-record signal that the artifact exists. If the ledger write fails, the artifact is in an inconsistent state — abort and surface the error so the operator can investigate.

5. **Mirror to cwd (best-effort)** — Copy `$ACTIVE_DIR/TLDR.md` to `./.stoobz/TLDR.md` (mkdir -p the parent first). If the mirror fails (permissions, no disk, etc.), log a warning to the operator in the format from [write-artifact-protocol.md § Mirror failure](../write-artifact-protocol.md):
   ```
   warn: cwd mirror failed for TLDR.md: <error>
         Durable write succeeded at <archive-path>.
         The artifact is preserved; only the working-dir copy is missing.
   ```
   The skill continues — the durable write is canonical.

6. Confirm to the operator: the archive path, the cwd path (or mirror-warning), and offer to adjust if needed.

## Output Format

```markdown
# TLDR: {One-line title}

**Date:** {YYYY-MM-DD}
**Session:** {branch or context identifier}
**Author:** Claude + {user}

---

## Context

{1-2 sentences: what prompted this work and why it matters}

## Key Findings

- {Finding 1 — be specific, include numbers/names}
- {Finding 2}
- {Finding 3}

## Decisions

| Decision           | Rationale |
| ------------------ | --------- |
| {What was decided} | {Why}     |

## Changes Made

- {File or system changed}: {what changed}

## Open Items

- [ ] {Next step or unresolved question}
- [ ] {Follow-up needed}

---

_Generated from Claude Code session — see full conversation for details._
```

## Rules

- **Brevity over completeness** — if it takes more than 2 minutes to read, it's too long
- **Specifics over generalities** — include actual file names, numbers, error messages, not vague descriptions
- **Skip sections with no content** — if no decisions were made, omit the Decisions table
- **No jargon expansion** — engineers reading this know the stack; don't explain what Oban or Ecto are
- **One file, flat structure** — no subdirectories, no companion files
- The canonical write location is `$ACTIVE_DIR/TLDR.md`; cwd `.stoobz/TLDR.md` is a best-effort mirror, not the source of truth
- The ledger entry's `name` is `TLDR.md` (no leading path; the artifact lives at the archive root)
