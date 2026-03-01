# Session Kit Guide

Workflows and composability patterns for getting the most out of Session Kit.

## New Repo Onboarding

Before your first real work session in a new repo, prime it:

```
/prime                          → analyzes codebase, creates expert skills + contexts
```

This creates permanent `.claude/skills/` and `.claude/commands/contexts/` files that every future session benefits from. Run it once — or `--refresh` when the codebase evolves:

```
/prime --refresh                → checks staleness, updates changed skills
```

The full onboarding flow:

```
Day 1:    /prime → expert skills created
Day 1+:   /pickup → [work with expert skills loaded] → /park
Months later: /prime --refresh → skills updated for architecture changes
```

## The Park → Pickup Cycle

The core loop. Park when you leave, pickup when you return.

```
Session 1:  [do work] → /park
Session 2:  /pickup → [continue] → /park
Session 3:  /pickup → [wrap up] → /park + /retro
```

`/park` generates three artifacts (TLDR, relay context, prompt analysis) in `./.stoobz/`, archives them to `~/.stoobz/sessions/`, and leaves `.stoobz/CONTEXT_FOR_NEXT_SESSION.md` as the relay baton. `/pickup` reads that file and presents a briefing so you can jump right back in.

## Ticket Work

When working on a ticket across sessions:

```
/park PROJ-1234                   → archives with the ticket ID as label
/pickup → [finish] → /handoff    → share findings with the team
/park                             → save final state
```

The label makes it easy to find later with `/index PROJ-1234`.

## Sharing with Teammates

Different skills for different audiences:

```
/tldr      → 2-minute read for Slack — "here's what I found"
/handoff   → full context for PR review or pairing — business context, evidence, recommendations
/rca       → investigation package — teammate drops INVESTIGATION_CONTEXT.md into their own Claude session
```

`/tldr` is for humans scanning quickly. `/handoff` is for humans who need full context. `/rca` is for humans + Claude working together.

## Mid-Session Persistence

Use `/persist` to save reference artifacts without ending your session:

```
[produce a comparison table] → /persist deployment-methods comparison infrastructure
[continue working]           → /persist api-runbook playbook deployment
```

Persisted artifacts land in `./.stoobz/` during the session and are archived to `~/.stoobz/sessions/<project>/` when you `/park`.

## Finding Past Work

```
/index                     → see all sessions
/index auth                → filter by tag, summary, label, or project
/index --deep "rate limit" → grep inside archived artifact content
```

The manifest powers fast lookups. `--deep` searches actual file content when metadata isn't enough.

## Production Investigation Flow

When debugging a production issue:

```
Session 1:  [investigate] → /rca         → package findings + evidence
                          → /park        → save your own session context

Teammate:   [paste INVESTIGATION_CONTEXT.md into Claude] → review → verify → fix
```

`/rca` produces three things: a quick-scan summary (human-readable), a deep context doc (Claude-droppable), and an `evidence/` directory with raw artifacts.

## Prompt Honing Loop

Track how your prompts evolve:

```
Session 1:  [work from initial prompt] → /hone
Session 2:  [paste optimized prompt from HONE.md] → [work] → /hone
            Compare: is the optimized prompt actually better?
```

## Retroactive Cleanup

If you have scattered `.stoobz/` directories from before you started using `/park`:

```
/park --archive-system                → interactive picker (default)
/park --archive-system --dry-run      → preview what would happen
/park --archive-system --all          → archive everything, no prompting
/park --archive-system --all --clean  → archive + remove originals
```

## End of Day

```
/park         → saves context + summary + prompt analysis → archives
/retro        → reflect on what worked (optional, /park archives it if present)
/handoff      → if teammates need to pick up tomorrow
```

## Crash Recovery

If a terminal crashes before `/park`, active sessions are still findable as long as any session-kit skill ran during the session (which triggers check-in):

```
/index --active    → all live sessions with resume commands
```

Copy the `return_to` command to drop back in:

```
cd ~/repos/brrp && claude --resume a1b2c3d4-...
```

If no session-kit skill ran during the session (no check-in), fall back to manual forensics:

```bash
find ~/.claude/projects/ -maxdepth 2 -name "*.jsonl" -mtime -1 | sort -t/ -k6 | tail -5
```

## Session Chains

Chains track a logical work stream across multiple park/pickup cycles, even across projects:

```
Session 1 (stoobz-api): /pickup → [work] → /park brrp-migration
Session 2 (stoobz-web): /pickup → [inherits chain] → [work] → /park
Session 3 (stoobz-web): /pickup → [inherits chain] → [work] → /park
```

Each `/park` writes chain metadata into the relay baton. Each `/pickup` inherits it and increments the position. The chain gets its name from the first `/park` label.

```
/index --chain                → see all chains grouped
/index --chain brrp-migration → see one chain's timeline
```

Chains are especially useful for long-running investigations or features that span days and cross project boundaries.

## Chain Branching with Checkpoint

When a multi-session investigation hits dead ends or you want to carry forward only the valuable parts:

```
Session 1:  [initial analysis] → /park
Session 2:  /pickup → [try approach A — works] → /park
Session 3:  /pickup → [try approach B — dead end] → /park
Session 4:  /pickup → [try approach C — partially useful] → /park
```

Now synthesize the good parts:

```
/checkpoint 1,2,4              → synthesize nodes 1, 2, 4 — skip the dead end in node 3
```

Or equivalently:

```
/checkpoint --exclude 3        → all nodes except 3
```

This produces a `CHECKPOINT_CONTEXT.md` (the synthesis) and a `CONTEXT_FOR_NEXT_SESSION.md` (the relay baton) that starts a new branch chain. The new chain knows where it came from — `/index --chain` shows the fork relationship.

In a new session:

```
/pickup                        → picks up from the checkpoint, briefing shows "branched from" info
```

### When to Checkpoint

- **After a long investigation** where some sessions were dead ends
- **Before changing direction** when you want to preserve what you've learned but start clean
- **When context is too noisy** — too many sessions carried forward, need to distill
- **To create focused starting points** for different team members working from the same research

### Checkpoint vs. Relay

| | `/relay` | `/checkpoint` |
|---|---------|---------------|
| Source | Current session | Selected chain nodes |
| Output | 1:1 relay baton | N:1 synthesis + relay baton |
| Chain effect | Extends chain linearly | Branches chain (creates DAG) |
| Dead ends | Carries everything forward | Prunes selectively |

### Viewing Chains and Branches

```
/index --chain                 → see all chains and fork relationships
/index --chain brrp-migration  → see specific chain + any branches from it
```

## Composability

Skills are independent — use any combination. Some natural pairings:

| Scenario | Skills |
|----------|--------|
| New repo setup | `/prime` → `/pickup` → `/park` |
| Solo deep dive | `/park` → `/pickup` → `/park` |
| Team handoff | `/tldr` + `/handoff` |
| Investigation | `/rca` + `/park` |
| Learning | `/hone` + `/retro` |
| Reference building | `/persist` + `/index` |
| Full ceremony | `/park` + `/retro` + `/handoff` |
| Prune dead ends | `/checkpoint 1,2,4` → `/pickup` |
| Branch from research | `/checkpoint` → `/pickup` → new direction |

## Tips

- **`/park` is the default exit** — It handles everything. Use individual skills only when you need a specific artifact without the full ceremony.
- **Labels help** — `/park fix-auth-bug` is easier to find than auto-generated labels.
- **Tags are automatic** — `/park` and `/persist` auto-detect tags from content. Override with explicit tags on `/persist` when the auto-detection misses.
- **Restart after skill edits** — Skill content is cached when Claude Code starts. Edit a SKILL.md → restart to pick it up.
- **`.stoobz/CONTEXT_FOR_NEXT_SESSION.md` stays in `.stoobz/`** — This is intentional. It's the relay baton. Don't move it.
