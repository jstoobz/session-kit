---
name: park
description: Park the current session by generating all session artifacts, archiving them to $SESSION_KIT_ROOT/sessions/<project>/<date-label>/ (default ~/.stoobz/), and updating the manifest. Use when the user says "/park", "park this session", "wrap up", "I'm done for now", "save everything", or wants to create a complete handoff package before leaving a session. Runs /tldr, /relay, and /hone in sequence, then archives. Supports --archive-system for retroactive cleanup of scattered .stoobz/ directories (with --select, --all, --dry-run, --clean flags).
---

# Park Session

End-of-session ceremony. Generate TLDR / RELAY / HONE, then finalize the active archive — rename `<sid>-active/` to `<date>-<label>/`, flip the manifest entry to `archived`, and append chain metadata to the relay baton.

Three `sk write-artifact` calls and one `sk park-finalize` call. The judgment (label resolution, tag inference, summary extraction) stays in this skill's prose; the durability, locking, and manifest math live in the binaries.

## Contract

- **Inputs:** optional `<label>` argument (e.g., `/park scripts-as-tools-substrate`); current conversation; current git state.
- **Outputs:** three artifacts in the durable archive (`TLDR.md`, `CONTEXT_FOR_NEXT_SESSION.md`, `HONE.md`); cwd mirror of the same; manifest entry for this session flipped from `active` → `archived`; chain metadata block appended to `./.stoobz/CONTEXT_FOR_NEXT_SESSION.md`.
- **Idempotent:** if the session is already archived, `sk park-finalize` is a friendly no-op — it surfaces the existing archive path and exits 0.

## Process

### 1. Announce

Tell the user: `Parking this session. Generating artifacts...`

### 2. Compose the three artifact bodies

For each of TLDR / RELAY / HONE, follow the body-composition prose in that skill's `Process` section (sections 1–4 of [tldr/SKILL.md](../tldr/SKILL.md), [relay/SKILL.md](../relay/SKILL.md), [hone/SKILL.md](../hone/SKILL.md)). Bind the resulting bodies to shell variables `$TLDR_BODY`, `$RELAY_BODY`, `$HONE_BODY`.

Read prior archive copies (`~/.stoobz/sessions/<project>/<sid>-active/<NAME>.md`) and weave their content under a `## Previous Session` heading if present — the rolling-history rule from each individual skill applies here too.

### 3. Write the three artifacts via the substrate

```bash
echo "$TLDR_BODY"  | sk write-artifact --skill park --artifact TLDR.md --content-stdin
echo "$RELAY_BODY" | sk write-artifact --skill park --artifact CONTEXT_FOR_NEXT_SESSION.md --content-stdin
echo "$HONE_BODY"  | sk write-artifact --skill park --artifact HONE.md --content-stdin
```

`--skill park` (not `tldr` / `relay` / `hone`) so the ledger attributes the writes to the park ceremony — "what wrote this artifact" stays answerable when /park runs the same artifacts the individual skills also produce.

Each call performs the four-step durable-first protocol: checkin precondition → archive write → verify → ledger append → cwd mirror. See [write-artifact-protocol.md](../write-artifact-protocol.md).

### 4. Resolve label (first match wins)

| Priority | Source | Use when |
|----------|--------|----------|
| 1 | `/park <label>` argument | Operator passed an explicit label |
| 2 | Git branch name | Branch is not `main` / `master` / `develop` |
| 3 | Slugified first heading of just-written `TLDR.md` | No useful branch name |
| 4 | (empty — date-only archive) | All else fails |

Slugify rules: lowercase, ASCII, alphanumeric + `-`, max 50 chars, no leading/trailing `-`.

### 5. Resolve summary

Use the title of the just-written TLDR (the text after `# TLDR: ` on the first heading line). If the heading is bare `# TLDR`, fall back to the first paragraph (1 line, ~80 chars max).

### 6. Auto-detect tags (2–5)

Scan `$TLDR_BODY` (case-insensitive) for matches in:

- **Languages:** elixir, python, javascript, typescript, ruby, go, rust, sql, bash, powershell
- **Frameworks:** phoenix, ecto, oban, react, next, absinthe, liveview
- **Topics:** debugging, performance, migration, refactor, investigation, auth, deployment, testing, infrastructure

Pick 2–5 most-mentioned terms. Tags are comma-separated in the next step. `sk park-finalize` merge-deduplicates these into the manifest entry's existing `tags[]` array, so any tags accumulated mid-session via `/persist` survive automatically — the orchestrator does not need to read the manifest or compute the union itself.

### 7. Finalize via the substrate

```bash
sk park-finalize --label "$LABEL" --summary "$SUMMARY" --tags "$TAGS"
```

`sk park-finalize`:

1. Reads the ledger (`<active-dir>/.session-artifacts.json`) as the authoritative artifact list, dedupe-by-name last-write-wins.
2. Verifies each ledger entry exists at `<active-dir>/<name>` — surfaces missing files as a warning, continues.
3. Renames `<sid>-active/` → `<YYYY-MM-DD>-<label>/` (with `-2`, `-3`, ... collision suffix).
4. Atomic manifest RMW: flips `status` to `archived`; populates `id`, `label`, `summary`, `date`, `archive_path`, `artifacts`; merge-dedupes the supplied `--tags` into the existing `tags[]` (insertion-order preserved). Respects inherited `chain_id`, `chain_position`, `previous_session_id`, `parent_chain_id`, `checkpoint_nodes`. If first-node (chain_position null or 1, chain_id null or == session_id), sets `chain_id` = `<label>`.
5. Appends `<!-- session-kit-chain ... -->` block to `./.stoobz/CONTEXT_FOR_NEXT_SESSION.md` (the relay baton stays in cwd for `/pickup`).
6. Prints summary (Archive path, Artifacts, Relay, Tags, Session UUID prefix, Chain).

## Arguments (orchestrator level)

| Position | Meaning | Default |
|----------|---------|---------|
| `<label>` | Override the label-resolution chain | (resolved per step 4) |

Pass-throughs the orchestrator may set on `sk park-finalize`:

| Flag | When to use |
|------|-------------|
| `--chain-id <id>` | Operator explicitly wants a different chain name (rare) |
| `--no-chain-block` | Operator explicitly suppresses chain metadata block (rare) |

## Exit Codes

`sk park-finalize` returns:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Session archived (or already archived — friendly no-op) | Done |
| `1` | Durability failure (rename, mkdir, manifest update) | Surface error; do not claim success |
| `2` | Warning (missing ledger artifacts, chain block append failed) | Mention the warning; archive itself is good |
| `3` | Usage error | Fix invocation |

The three `sk write-artifact` calls follow their own exit-code table — see [write-artifact-protocol.md](../write-artifact-protocol.md). If any of them returns 1, abort the orchestrator before calling `sk park-finalize` — partial archives are not finalizable.

## `--archive-system` — Retroactive Cleanup

When invoked as `/park --archive-system`, skip the Process above and run the retroactive cleanup flow for legacy scattered `.stoobz/` directories. This mode is **operator-driven, interactive, and rarely runs** — it has not been migrated to a `sk` subcommand and remains prose-driven here.

See the dedicated reference doc (TODO Phase 2D): `park/archive-system.md`. Until that lands, the prose for `--archive-system` lives in commit `4234da7^` of this skill (pre-Phase-2C version) — pull it back from git history if/when the flow is needed.

The supported flags (`--select` default, `--all`, `--dry-run`, `--clean`) and their semantics are unchanged from the pre-Phase-2C spec.

## Rules

- **All or nothing** — Generate all three core artifacts (TLDR + RELAY + HONE). For individual artifacts, use the specific skill directly.
- **Always finalize** — After writes succeed, `sk park-finalize` runs automatically. No flag needed.
- **No questions** — Generate all three without asking. Use best judgment for label and tags.
- **Don't re-explain** — Just execute. The user wants results, not descriptions.
- **CONTEXT_FOR_NEXT_SESSION.md stays in cwd** — The mirror is the relay baton `/pickup` reads next session. `sk park-finalize` appends the chain block to it after finalization.
- **Idempotent re-park** — If the session is already archived, `sk park-finalize` exits 0 with a "nothing to do" message. The original archive is preserved.
- **Respect inherited chain metadata** — If `/pickup` inherited chain fields, `sk park-finalize` keeps them. The substrate handles this; the orchestrator does not need to reason about it.

## See also

- [tldr/SKILL.md](../tldr/SKILL.md), [relay/SKILL.md](../relay/SKILL.md), [hone/SKILL.md](../hone/SKILL.md) — body composition rules
- [checkin/SKILL.md](../checkin/SKILL.md) — precondition each `sk write-artifact` triggers internally
- [write-artifact-protocol.md](../write-artifact-protocol.md) — the durable-first contract
- `sk park-finalize --help`, `sk write-artifact --help` — full arg / exit-code / JSON reference
- ADR-0004 (Session Kit artifact durability) — why /park is finalization, not copy
- ADR-0005 (Skills as thin orchestrators of versioned scripts) — why this skill is a thin wrapper
