---
name: handoff
description: Generate a HANDOFF.md for sharing investigation results or session context with teammates who weren't involved. Use when the user says "/handoff", "share this with the team", "write up for others", "teammate summary", or needs to create documentation for someone unfamiliar with the session. Unlike /tldr (quick scan) or /relay (Claude-to-Claude), this is human-to-human communication with full context.
---

# Handoff

Generate a `HANDOFF.md` for sharing with teammates who need full context on what happened.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Session Check-In (silent — before main process)

On first invocation of any session-kit skill in this session, register the active session in the manifest. See [session-checkin.md](../session-checkin.md) for the full protocol. Summary:

1. Detect session ID from most recently modified `.jsonl` in `~/.claude/projects/$(pwd | tr '/' '-')/` (fallback: git root encoding). If detection fails, skip silently.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create if missing).
3. If no entry with this `session_id` exists → create active registration (`status: "active"`, `session_id`, `return_to`, `started_at`, `last_activity`, `last_exchange`, `skills_used`, nulls for label/summary/archive_path).
4. If entry exists → update `last_activity`, `last_exchange`, append this skill to `skills_used`.
5. Write manifest. Proceed to main process. No output about check-in.

## Process

1. **Check for existing file** — Read `./.stoobz/HANDOFF.md` if it exists. If found:
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

4. Write `.stoobz/HANDOFF.md` in the current working directory.

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
- Write to `./.stoobz/HANDOFF.md` unless the user specifies a different path
