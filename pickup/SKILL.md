---
name: pickup
description: Resume a session by loading prior context from artifacts. Use when the user says "/pickup", "pick up where I left off", "resume", "load context", or starts a new session in a directory that has CONTEXT_FOR_NEXT_SESSION.md or TLDR.md files. Reads existing session artifacts and primes Claude with full context so the user doesn't have to re-explain anything.
---

# Pickup

Load prior session artifacts and get up to speed instantly. The complement to `/park`.

## Process

1. **Scan for artifacts** in the current working directory:
   - `CONTEXT_FOR_NEXT_SESSION.md` (primary — contains full resume context)
   - `TLDR.md` (secondary — provides session summary)
   - `PROMPT_LAB.md` (tertiary — shows original goals and optimized prompt)
   - `RETRO.md` (if present — shows lessons from last session)

2. **Load in priority order:**
   - Read `CONTEXT_FOR_NEXT_SESSION.md` first — this has everything needed
   - If missing, fall back to `TLDR.md` for at least a summary
   - If neither exists, tell the user: "No session artifacts found in {cwd}. Starting fresh."

3. **Load recommended skills** — If the relay doc lists skills under "Skills To Load", invoke them.

4. **Present a briefing:**

```
Picked up from {date}. Here's where we are:

  What: {1-line summary of the work}
  Where: {specific stopping point}
  Next: {top priority action}

Ready to continue. What would you like to tackle first?
```

5. **If the user pastes a CONTEXT_FOR_NEXT_SESSION.md directly** (instead of running `/pickup`), recognize it and treat it the same — no need to re-read files.

## Rules

- **Don't parrot the full document** — Summarize into the briefing format. The user can read the files.
- **Load skills silently** — Don't announce each skill load, just do it.
- **Ask before acting** — Present the briefing and wait for direction. Don't start executing next steps autonomously.
- **Handle stale context** — If the artifact is more than 7 days old, note this: "Context is from {date} — things may have changed."
