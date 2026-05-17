---
name: pickup
description: Resume a session by loading prior context from artifacts. Use when the user says "/pickup", "pick up where I left off", "resume", "load context", or starts a new session in a directory that has CONTEXT_FOR_NEXT_SESSION.md or TLDR.md files. Reads existing session artifacts and primes Claude with full context so the user doesn't have to re-explain anything.
---

# Pickup

Load prior session artifacts and get up to speed instantly. The complement to `/park`.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Check-In (precondition)

Before the Process section runs, invoke `sk checkin --silent --invoking pickup` as a precondition. Pass `--inherit-chain-from` so chain metadata on the relay baton flows into the new session's manifest entry at first-checkin. See [checkin/SKILL.md](../checkin/SKILL.md) for the protocol details (three-tier session-ID resolution, active-dir + ledger creation, scaffolding-idempotent re-entry with liveness refresh, and the chain-inheritance flag semantics).

If `sk checkin` aborts (mkdir or ledger creation failure — the only durability conditions that fail loudly), this skill aborts too. Do not proceed to the Process section. Do not write any artifact.

### Reference Invocation

```bash
BATON="./.stoobz/CONTEXT_FOR_NEXT_SESSION.md"
if [ ! -f "$BATON" ] && [ -f "./.stoobz/CHECKPOINT_CONTEXT.md" ]; then
  BATON="./.stoobz/CHECKPOINT_CONTEXT.md"
fi
sk checkin --silent --invoking pickup --inherit-chain-from "$BATON"
```

`--inherit-chain-from` is silent-fallthrough on a missing path or missing chain block — pass it unconditionally. Legacy / first-session pickups (no baton, no chain block) leave chain fields null exactly like before.

### Chain Inheritance Semantics

Chain inheritance is enforced by the binary, not by skill prose:

- `chain_id` from the baton → manifest `chain_id`
- baton `session_id` → manifest `previous_session_id` (the PARKED session you're picking up)
- baton `chain_position` + 1 → manifest `chain_position` (this new session is the next link)
- baton `parent_chain_id`, `checkpoint_nodes` → pass through to manifest if present (checkpoint-originated chains)

Chain fields are write-once at first-checkin; re-entry preserves them. See [checkin/SKILL.md § Chain Inheritance](../checkin/SKILL.md#chain-inheritance) for the full flag reference.

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
