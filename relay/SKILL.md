---
name: relay
description: Generate a CONTEXT_FOR_NEXT_SESSION.md that captures everything needed to resume work in a new Claude Code session without re-explaining. Use when the user says "/relay", "save context", "context for next session", "I need to pick this up later", or wants to preserve session state for continuation. Produces a structured handoff document optimized for pasting into a new session. Like a relay race — passing the baton to the next session.
---

# Context For Next Session

Compose a machine-readable session-resumption document in conversation; hand it to `sk write-artifact`, which checks in, writes the archive durably, appends a ledger entry, and mirrors to `cwd/.stoobz/CONTEXT_FOR_NEXT_SESSION.md`. One binary call handles every mechanical step.

## Process

1. **Rolling history — read the previous archive first.** Before composing the new body, read the active-archive's prior copy if it exists. Path: `~/.stoobz/sessions/<project>/<sid>-active/CONTEXT_FOR_NEXT_SESSION.md` (or whatever `SESSION_KIT_ROOT` resolves to). If present, the new body keeps the latest content on top and tucks the prior content under a `## Previous Session Context` heading. Merge open items: check off completed ones, carry forward what remains.

2. **Gather session state**:
   - Current git branch, uncommitted changes, recent commits
   - Working directory and key file paths referenced in conversation
   - Environment details (which env was targeted: local, QA, UAT, prod)
   - Skills invoked during this session (scan conversation for `/skill-name` invocations; exclude session-kit lifecycle skills)

3. **Extract from conversation**:
   - What we were working on and why
   - Where we left off (specific point of progress)
   - Decisions made that constrain future work
   - Key files/modules/paths that are relevant
   - Known issues, blockers, or gotchas discovered
   - Suggested next actions in priority order

4. **Compose `RELAY_BODY`** in the [Output Format](#output-format) below. Skip sections with no content.

5. **Single bash invocation** — pipe `RELAY_BODY` into the binary:

   ```bash
   sk write-artifact --skill relay --artifact CONTEXT_FOR_NEXT_SESSION.md --content-stdin <<< "$RELAY_BODY"
   ```

   Confirmation prints; the cwd path appears unless the mirror failed (a warning is surfaced; the archive write is still good).

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

- `/beam-expert` — OTP process debugging
- `/use-db` — queried UAT eventstore

---

_Paste this document at the start of your next Claude Code session in this directory._
```

## Exit Codes

`sk write-artifact` returns:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Durable write + mirror both succeeded | Done |
| `1` | Durability failure (archive, verify, ledger, or precondition checkin) | Surface error; do not claim success |
| `2` | Durable write succeeded; cwd mirror failed (warning already on stderr) | Mention the warning; the archive is authoritative |
| `3` | Usage error (bad args) | Fix invocation |

## Rules

- **Optimized for machine consumption** — this is for Claude to read, not just humans. Be precise about paths, branch names, and state.
- **Include the "why" not just the "what"** — next session needs to understand intent, not just facts.
- **Concrete over abstract** — "check `lib/my_app/accounts/projectors/user_projector.ex` line 42" beats "look at the projector."
- **Skip sections with no content** — don't include empty Gotchas or Decisions sections.
- **Auto-detect skills** — Scan the conversation for skill invocations (`/beam-expert`, `/use-db`, etc.). Exclude session-kit lifecycle skills (`/park`, `/relay`, `/tldr`, `/pickup`, `/hone`, `/retro`, `/handoff`, `/rca`, `/index`, `/persist`, `/sweep`, `/prime`, `/checkin`) — those are infrastructure, not domain context.
- The canonical write location is `<active-archive>/CONTEXT_FOR_NEXT_SESSION.md`; `cwd/.stoobz/CONTEXT_FOR_NEXT_SESSION.md` is the best-effort mirror.
- The ledger entry's `name` is `CONTEXT_FOR_NEXT_SESSION.md`.

## See also

- [checkin/SKILL.md](../checkin/SKILL.md) — the precondition `sk write-artifact` invokes silently
- [write-artifact-protocol.md](../write-artifact-protocol.md) — the durable-first contract
- `sk write-artifact --help` — full arg + exit-code + JSON-schema reference
