---
name: tldr
description: Generate a concise TLDR.md summary of the current session's key findings, decisions, and outcomes. Use when the user says "/tldr", "write a tldr", "summarize this session", "create a summary", or wants a shareable document capturing what happened in this conversation. Produces a clean, engineer-friendly markdown file ready to share before diving into full analysis.
---

# TLDR

Compose a session summary in conversation; hand it to `sk write-artifact`, which checks in, writes the archive durably, appends a ledger entry, and mirrors to `cwd/.stoobz/TLDR.md`. The single binary call handles every mechanical step.

## Process

1. **Conversation review** (Claude analysis — no shell). Extract from the current session:
   - **Context** — what was investigated or built, and why it matters
   - **Key findings** — discoveries, root causes, concrete data points (file names, error messages, numbers)
   - **Decisions** — choices made, with rationale
   - **Changes** — files / systems modified, commands run
   - **Open items** — unresolved questions, follow-ups, next steps

2. **Compose `TLDR_BODY`** in the [Output Format](#output-format) below. Skip sections with no content. Brevity over completeness — if it takes more than ~2 minutes to read, it is too long.

   If a prior TLDR for this session already exists in the archive, the binary does not append it for you. To preserve a rolling history, read `~/.stoobz/sessions/<project>/<sid>-active/TLDR.md` first and weave the prior content under a `## Previous Session` heading in your new body.

3. **Single bash invocation** — pipe `TLDR_BODY` into the binary:

   ```bash
   sk write-artifact --skill tldr --artifact TLDR.md --content-stdin <<< "$TLDR_BODY"
   ```

   The binary internally calls `sk checkin --silent --invoking tldr`, then writes the archive, verifies, appends the ledger, and mirrors to cwd. Confirmation is printed; the cwd path appears unless the mirror failed (a warning is surfaced; the durable write is still good).

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

## Decisions

| Decision           | Rationale |
| ------------------ | --------- |
| {What was decided} | {Why}     |

## Changes Made

- {File or system changed}: {what changed}

## Open Items

- [ ] {Next step or unresolved question}

---

_Generated from Claude Code session — see full conversation for details._
```

## Exit Codes

`sk write-artifact` returns:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Durable write + mirror both succeeded | Done |
| `1` | Durability failure (archive, verify, ledger, or precondition checkin) | Surface error; do not claim success |
| `2` | Durable write succeeded; cwd mirror failed (warning already on stderr) | Mention the warning to the user; the archive is still authoritative |
| `3` | Usage error (bad args) | Fix invocation |

## Rules

- **Brevity over completeness** — if reading takes more than 2 minutes, it's too long.
- **Specifics over generalities** — actual file names, numbers, error messages.
- **Skip empty sections** — no decisions made? Omit the table.
- **No jargon expansion** — engineers reading this know the stack.
- **One file, flat structure** — `TLDR.md` only; no companion files for this skill.
- The canonical write location is `<active-archive>/TLDR.md`; `cwd/.stoobz/TLDR.md` is a best-effort mirror, not the source of truth.
- The ledger entry's `name` is `TLDR.md` (no leading path; the artifact lives at the archive root).

## See also

- [checkin/SKILL.md](../checkin/SKILL.md) — the precondition `sk write-artifact` invokes silently
- [write-artifact-protocol.md](../write-artifact-protocol.md) — the durable-first contract this binary implements
- `sk write-artifact --help` — full arg + exit-code + JSON-schema reference
