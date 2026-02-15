---
name: handoff
description: Generate a HANDOFF.md for sharing investigation results or session context with teammates who weren't involved. Use when the user says "/handoff", "share this with the team", "write up for others", "teammate summary", or needs to create documentation for someone unfamiliar with the session. Unlike /tldr (quick scan) or /relay (Claude-to-Claude), this is human-to-human communication with full context.
---

# Handoff

Generate a `HANDOFF.md` for sharing with teammates who need full context on what happened.

## Process

1. **Check for existing file** — Read `./HANDOFF.md` if it exists. If found:
   - Preserve previous versions under a `## Previous Handoff` heading
   - Add new content as the primary section

2. **Extract from conversation:**
   - The problem/task and why it matters (business context, not just technical)
   - What was tried and what was learned
   - Current state — what's done, what's not
   - Recommendations with rationale
   - Any risks, caveats, or "watch out for" items
   - Links to relevant files, PRs, Jira tickets, dashboards

3. **Calibrate audience** — This is for engineers who:
   - Know the codebase but weren't in this session
   - Need enough context to take over or review the work
   - Don't need to know about Claude skills, prompt iterations, or session mechanics

4. Write `HANDOFF.md` in the current working directory.

## Output Format

```markdown
# Handoff: {Descriptive title}

**Date:** {YYYY-MM-DD}
**Author:** {user}
**Ticket:** {Jira ticket if applicable}
**Branch:** {git branch}

---

## Background

{Why this work happened — the business problem or technical need. 2-3 sentences.}

## What Was Done

{Chronological or logical summary of the work. Include specifics.}

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

## Rules

- **No Claude artifacts** — Strip references to skills, prompts, session mechanics. This is for humans.
- **Business context first** — Start with "why" before "what". Teammates need to understand importance.
- **Evidence-based** — Include actual numbers, error messages, query results. Not "it seems slow" but "p99 latency hit 4.2s."
- **Actionable recommendations** — Each recommendation should have enough context that someone can act on it without asking follow-up questions.
- **Link everything** — Jira tickets, PRs, dashboards, relevant files. Make it easy to dig deeper.
- **Skip sections with no content** — Don't include empty Risks or References sections.
- Write to `./HANDOFF.md` unless the user specifies a different path
