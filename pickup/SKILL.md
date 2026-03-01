---
name: pickup
description: Resume a session by loading prior context from artifacts. Use when the user says "/pickup", "pick up where I left off", "resume", "load context", or starts a new session in a directory that has CONTEXT_FOR_NEXT_SESSION.md or TLDR.md files. Reads existing session artifacts and primes Claude with full context so the user doesn't have to re-explain anything.
---

# Pickup

Load prior session artifacts and get up to speed instantly. The complement to `/park`.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Session Check-In (silent — before main process)

On first invocation of any session-kit skill in this session, register the active session in the manifest. See [session-checkin.md](../session-checkin.md) for the full protocol. Summary:

1. Detect session ID from most recently modified `.jsonl` in `~/.claude/projects/$(pwd | tr '/' '-')/` (fallback: git root encoding). If detection fails, skip silently.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create if missing).
3. If no entry with this `session_id` exists → create active registration (`status: "active"`, `session_id`, `return_to`, `started_at`, `last_activity`, `last_exchange`, `skills_used`, nulls for label/summary/archive_path).
4. If entry exists → update `last_activity`, `last_exchange`, append this skill to `skills_used`.
5. Write manifest. Proceed to main process. No output about check-in.

### Chain Inheritance (pickup-specific)

After loading the relay baton (step 2 below), extract chain metadata from `CONTEXT_FOR_NEXT_SESSION.md`:

1. Look for a `<!-- session-kit-chain ... -->` comment block containing `chain_id`, `session_id`, `chain_position`.
2. If found, during check-in registration set:
   - `chain_id` = inherited chain_id from relay baton
   - `previous_session_id` = the session_id from the relay baton (the parked session)
   - `chain_position` = inherited chain_position + 1
   - `parent_chain_id` = inherited if present (checkpoint-originated chains)
   - `checkpoint_nodes` = inherited if present (checkpoint-originated chains)
3. If no chain metadata in relay baton (legacy context): start a new chain — leave chain fields null (same as first-session behavior). `/park` will assign chain identity later.

## Process

1. **Scan for artifacts** in `./.stoobz/`:
   - `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` (primary — contains full resume context)
   - `.stoobz/CHECKPOINT_CONTEXT.md` (if present — checkpoint synthesis from prior chain)
   - `.stoobz/TLDR.md` (secondary — provides session summary)
   - `.stoobz/HONE.md` (tertiary — shows original goals and optimized prompt)
   - `.stoobz/RETRO.md` (if present — shows lessons from last session)

2. **Load in priority order:**
   - Read `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` first — this has everything needed
   - If missing, fall back to `.stoobz/TLDR.md` for at least a summary
   - If neither exists, tell the user: "No session artifacts found in `./.stoobz/`. Starting fresh."

3. **Load recommended skills** — If the relay doc lists skills under "Skills To Load", invoke them.

4. **Present a briefing:**

```
Picked up from {date}. Here's where we are:

  What:  {1-line summary of the work}
  Where: {specific stopping point}
  Next:  {top priority action}
  Chain: {chain_id} (session {N})        ← only if chain metadata was inherited

Ready to continue. What would you like to tackle first?
```

- If chain metadata was inherited from the relay baton, include the Chain line showing the `chain_id` and the new `chain_position`.
- If checkpoint metadata (`parent_chain_id`, `checkpoint_nodes`) is present, use this form instead:
  ```
  Picked up from checkpoint. Starting chain: {chain_id} (branched from {parent_chain_id}, nodes {checkpoint_nodes}).
  ```
- If no chain metadata (legacy context or first session), omit the Chain line.

5. **If the user pastes a CONTEXT_FOR_NEXT_SESSION.md directly** (instead of running `/pickup`), recognize it and treat it the same — no need to re-read files. Still extract chain metadata from the pasted content if present.

## Rules

- **Don't parrot the full document** — Summarize into the briefing format. The user can read the files.
- **Load skills silently** — Don't announce each skill load, just do it.
- **Ask before acting** — Present the briefing and wait for direction. Don't start executing next steps autonomously.
- **Handle stale context** — If the artifact is more than 7 days old, note this: "Context is from {date} — things may have changed."
- **Chain metadata flows through** — If the relay baton has chain metadata, preserve it. The chain_id and position carry forward to this session's manifest entry and eventual `/park` archive. Checkpoint metadata (`parent_chain_id`, `checkpoint_nodes`) also flows through so `/park` can archive it.
- **CHECKPOINT_CONTEXT.md is supplementary** — If both CONTEXT_FOR_NEXT_SESSION.md and CHECKPOINT_CONTEXT.md exist, the relay baton is primary. The checkpoint context provides additional background (the full synthesis). Read it for context but don't duplicate its content in the briefing.
