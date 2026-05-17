---
name: handoff
description: Generate a HANDOFF.md for sharing investigation results or session context with teammates who weren't involved. Use when the user says "/handoff", "share this with the team", "write up for others", "teammate summary", or needs to create documentation for someone unfamiliar with the session. Unlike /tldr (quick scan) or /relay (Claude-to-Claude), this is human-to-human communication with full context.
---

# Handoff

Generate a `HANDOFF.md` for sharing with teammates who need full context on what happened. This is human-to-human communication; strip session mechanics and Claude artifacts. Compose the body in conversation; `sk write-artifact` writes durably, appends the ledger, and mirrors to `cwd/.stoobz/HANDOFF.md`.

## Process

1. **Rolling history — read the previous archive first.** If `~/.stoobz/sessions/<project>/<sid>-active/HANDOFF.md` exists, preserve its prior content under a `## Previous Handoff` heading; new content goes on top.

2. **Extract from conversation**:
   - The problem / task and why it matters (business context, not just technical)
   - What was tried and what was learned
   - Current state — what's done, what's not
   - Recommendations with rationale
   - Any risks, caveats, or "watch out for" items
   - Links to relevant files, PRs, Jira tickets, dashboards

3. **Calibrate audience** — engineers who:
   - Know the codebase but weren't in this session
   - Need enough context to take over or review the work
   - Don't need to know about Claude skills, prompt iterations, or session mechanics

4. **Compose `HANDOFF_BODY`** in the [Output Format](#output-format) below, then a single bash invocation:

   ```bash
   sk write-artifact --skill handoff --artifact HANDOFF.md --content-stdin <<< "$HANDOFF_BODY"
   ```

## Output Format

```markdown
# Handoff: {Descriptive title}

**Date:** {YYYY-MM-DD}
**Author:** {user}
**Ticket:** {Jira ticket if applicable}
**Branch:** {git branch}

---

## Background

{Why this work happened — business problem or technical need. 2-3 sentences.}

## What Was Done

{Chronological or logical summary. Include specifics.}

### Key Findings

- {Finding with evidence — data points, error messages, measurements}

### Changes Made

- `{file}`: {what and why}

## Current State

{What's working, what's not, what's partially done}

## Recommendations

1. {Action item with rationale}
2. {Action item with rationale}

## Risks & Caveats

- {Thing that could bite someone who picks this up}

## References

- [{Jira ticket}]({url})
- [{Dashboard/monitoring}]({url})
- [{Related PR}]({url})

---

_Handoff generated {date} — reach out to {author} for questions._
```

## Exit Codes

`sk write-artifact` returns:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Durable write + mirror both succeeded | Done |
| `1` | Durability failure | Surface error; do not claim success |
| `2` | Durable write succeeded; cwd mirror failed | Mention the warning; archive is authoritative |
| `3` | Usage error | Fix invocation |

## Rules

- **No Claude artifacts** — strip references to skills, prompts, session mechanics. This is for humans.
- **Business context first** — start with "why" before "what".
- **Evidence-based** — actual numbers, error messages, query results. Not "it seems slow" but "p99 latency hit 4.2s."
- **Actionable recommendations** — enough context per item that a teammate can act without asking follow-up questions.
- **Link everything** — Jira tickets, PRs, dashboards, relevant files.
- **Skip empty sections** — no empty Risks or References blocks.
- The canonical write location is `<active-archive>/HANDOFF.md`; `cwd/.stoobz/HANDOFF.md` is the best-effort mirror.
- The ledger entry's `name` is `HANDOFF.md`.

## See also

- [checkin/SKILL.md](../checkin/SKILL.md), [write-artifact-protocol.md](../write-artifact-protocol.md)
- `sk write-artifact --help`
- [ADR-0005](~/.stoobz/kb/adr/0005-skills-as-thin-orchestrators-of-versioned-scripts.md)
