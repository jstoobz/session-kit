---
name: relay
description: Generate a CONTEXT_FOR_NEXT_SESSION.md that captures everything needed to resume work in a new Claude Code session without re-explaining. Use when the user says "/relay", "save context", "context for next session", "I need to pick this up later", or wants to preserve session state for continuation. Produces a structured handoff document optimized for pasting into a new session. Like a relay race — passing the baton to the next session.
---

# Context For Next Session

Generate a `CONTEXT_FOR_NEXT_SESSION.md` that enables a new Claude session to resume work with zero re-explanation.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Session Check-In (silent — before main process)

On first invocation of any session-kit skill in this session, register the active session in the manifest. See [session-checkin.md](../session-checkin.md) for the full protocol. Summary:

1. Detect session ID from most recently modified `.jsonl` in `~/.claude/projects/$(pwd | tr '/' '-')/` (fallback: git root encoding). If detection fails, skip silently.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create if missing).
3. If no entry with this `session_id` exists → create active registration (`status: "active"`, `session_id`, `return_to`, `started_at`, `last_activity`, `last_exchange`, `skills_used`, nulls for label/summary/archive_path).
4. If entry exists → update `last_activity`, `last_exchange`, append this skill to `skills_used`.
5. Write manifest. Proceed to main process. No output about check-in.

## Process

1. **Check for existing file** — Read `./.stoobz/CONTEXT_FOR_NEXT_SESSION.md` if it exists. If found:
   - Preserve previous context under a `## Previous Session Context` heading
   - Add new content as the primary (top) section with updated timestamp
   - Merge open items: check off completed ones, carry forward remaining

2. **Gather session state:**
   - Current git branch, uncommitted changes, recent commits
   - Working directory and key file paths referenced in conversation
   - Environment details (which env was targeted: local, QA, UAT, prod)
   - Skills invoked during this session (scan conversation for `/skill-name` invocations)

3. **Extract from conversation:**
   - What we were working on and why
   - Where we left off (specific point of progress)
   - Decisions made that constrain future work
   - Key files/modules/paths that are relevant
   - Known issues, blockers, or gotchas discovered
   - Suggested next actions in priority order

4. Write `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` in the current working directory.

5. Confirm the file path.

## Output Format

```markdown
# Context For Next Session

**Date:** {YYYY-MM-DD}
**Branch:** {current git branch}
**Working Dir:** {cwd}
**Last Session:** {1-line summary of what was accomplished}

---

## What We're Working On

{2-3 sentences: the goal, why it matters, and current approach}

## Where We Left Off

{Specific stopping point — what was the last thing done/attempted}

## Key Context

### Relevant Files

- `{path/to/file}` — {why it matters}

### Environment State

- **Branch:** {branch name} — {clean/dirty, ahead/behind}
- **Target env:** {local/QA/UAT/prod}
- **Dependencies:** {anything unusual about current state}

### Decisions Made

- {Decision}: {rationale} — constrains {what}

### Gotchas & Discoveries

- {Thing that wasn't obvious but matters}

## Next Steps

1. {Highest priority next action}
2. {Second priority}
3. {Third priority}

## Skills To Load

{Auto-populated from skills invoked during this session. List each skill that was
actively used (not just mentioned). Include a brief note on what it was used for.
If no skills were invoked beyond session-kit lifecycle commands, omit this section.}

- `/beam-expert` — OTP process debugging
- `/use-db` — queried UAT eventstore

---

_Paste this document at the start of your next Claude Code session in this directory._
```

## Rules

- **Optimized for machine consumption** — this is for Claude to read, not just humans. Be precise about paths, branch names, and state.
- **Include the "why" not just the "what"** — next session needs to understand intent, not just facts
- **Concrete over abstract** — "check `lib/my_app/accounts/projectors/user_projector.ex` line 42" beats "look at the projector"
- **Skip sections with no content** — don't include empty Gotchas or Decisions sections
- **Auto-detect skills** — Scan the conversation for skill invocations (commands like `/beam-expert`, `/use-db`, etc.) and list them in Skills To Load. Exclude session-kit lifecycle skills (`/park`, `/relay`, `/tldr`, `/pickup`, `/hone`, `/retro`, `/handoff`, `/rca`, `/index`, `/persist`, `/sweep`, `/prime`) — those are infrastructure, not domain context.
- **Skills recommendation** — always include which skills were loaded/useful so the next session can load them immediately
- Write to `./.stoobz/CONTEXT_FOR_NEXT_SESSION.md` unless the user specifies a different path
