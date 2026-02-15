---
name: tldr
description: Generate a concise TLDR.md summary of the current session's key findings, decisions, and outcomes. Use when the user says "/tldr", "write a tldr", "summarize this session", "create a summary", or wants a shareable document capturing what happened in this conversation. Produces a clean, engineer-friendly markdown file ready to share before diving into full analysis.
---

# TLDR

Generate a `TLDR.md` file summarizing the current session for sharing with other engineers.

## Process

1. **Check for existing file** — Read `./TLDR.md` if it exists. If found:
   - Preserve previous content under a `## Previous Session` heading
   - Add new content as the primary (top) section with updated timestamp
   - This creates a rolling history — latest session first

2. Review the full conversation to extract:
   - **What was investigated/built** — the problem or task
   - **Key findings** — discoveries, root causes, data points
   - **Decisions made** — choices and their rationale
   - **Actions taken** — code changes, config updates, commands run
   - **Open items** — unresolved questions, next steps, follow-ups

3. Write `TLDR.md` in the current working directory using the format below.

4. Confirm the file path and offer to adjust if needed.

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
- Write to `./TLDR.md` in the current working directory unless the user specifies a different path
