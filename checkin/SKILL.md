---
name: checkin
description: Register the current Claude Code session under Session Kit and pre-allocate the durable archive + ledger that other session-kit skills depend on. Use when the user says "/checkin", "register this session", "set up session kit here", "start a session", or starts working in a scratch / unfilled cwd and wants explicit Session Kit affordances before any artifact-writing skill fires. Also invoked silently as a precondition by every other artifact-producing session-kit skill (tldr, relay, hone, retro, handoff, rca, persist, park, pickup, checkpoint, prime).
---

# Check-In

Register the current Claude Code session in `$SESSION_KIT_ROOT/manifest.json`, pre-allocate `<archive>/<session-id>-active/`, and initialize `.session-artifacts.json`. Idempotent on re-entry — scaffolding is write-once; liveness fields (`last_activity`, `last_exchange`) refresh every call.

The implementation is the `sk checkin` binary (`bin/sk`, symlinked to `~/.local/bin/sk` by `link.sh`). This skill is a thin orchestrator — Claude runs one bash invocation and lets the binary handle resolution, scaffolding, manifest RMW, JSONL extraction, and locking. See ADR-0005 (Skills as thin orchestrators of versioned scripts) for why.

## Two Modes

| Mode | Trigger | On first check-in | On re-entry | On durability failure | Appends to `skills_used` |
|------|---------|-------------------|-------------|----------------------|---------------------------|
| **Explicit** | User typed `/checkin` | `Session checked in: <sid> → <archive>; ledger initialized (resolved via <tier>)` | `Already checked in: <sid>` | Abort caller, surface error | `"checkin"` |
| **Silent** | Another skill invokes as a precondition | (no output) | (no output) | Abort caller, surface error | The invoking skill's name (if `--invoking <skill>` passed); else nothing |

If both `--explicit` and `--invoking` are supplied, explicit wins — `"checkin"` is appended and the invoking value is ignored. This rule exists for the rare case a user types `/checkin` from inside another skill's flow.

## Invocation

User-invoked `/checkin`:

```bash
sk checkin --explicit
```

Silent precondition from another skill:

```bash
sk checkin --silent --invoking <skill-name>
```

Most callers never issue this themselves: artifact-writing skills go through `sk write-artifact`, which runs the checkin precondition in-process with their name (see [tldr/SKILL.md](../tldr/SKILL.md)). Direct invocation is for skills that register without an up-front artifact write — `/pickup` (which adds `--inherit-chain-from`) and `/prime`. From this skill's perspective, every call is one process.

## Arguments

| Flag | Effect |
|------|--------|
| `--explicit` | User-invoked mode. Emits success / re-entry message; appends `"checkin"` to `skills_used`. |
| `--silent` | Precondition mode. No stdout on success. |
| `--invoking <skill>` | Only meaningful with `--silent`. The named skill is appended to `skills_used` instead of `"checkin"`. |
| `--chain-id <id>` | Explicit `chain_id` for the new entry. First-checkin only; ignored on re-entry. |
| `--previous-session-id <sid>` | Explicit `previous_session_id`. First-checkin only. |
| `--chain-position <n>` | Explicit `chain_position`. First-checkin only. |
| `--parent-chain-id <id>` | Explicit `parent_chain_id` for checkpoint-originated chains. First-checkin only. |
| `--checkpoint-nodes <csv>` | Comma-separated integer list stored as `checkpoint_nodes`. Rejects non-numeric tokens with exit 3. First-checkin only. |
| `--inherit-chain-from <path>` | Parse a `<!-- session-kit-chain ... -->` block from the relay baton at `<path>` and populate chain fields. Individual `--chain-*` flags override. Silent fallthrough on missing file / missing block. First-checkin only. |
| `--json` | Emit a single JSON object on stdout instead of the human message. Schema: `{session_id, active_dir, ledger, manifest, resolved_via, is_first, mode, appended_skill}`. |
| `--debug` | Print resolution + path debug info to stderr. |

## Exit Codes

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Success (new check-in or re-entry) | Continue |
| `1` | Durability failure (mkdir / ledger / manifest write) | **Abort** the calling skill; do not write any artifact |
| `3` | Usage error (bad args) | Fix invocation |

## What the binary does

1. **Resolve session-id** via the three-tier chain — first non-empty wins:
   - **Tier 1 `jsonl`** — most-recent `*.jsonl` under `~/.claude/projects/<cwd-encoded>/`
   - **Tier 2 `git-root`** — same lookup against the git repo root's encoded path
   - **Tier 3a `cached`** — `cwd/.stoobz/.session-id` (set on a previous tier-3 invocation)
   - **Tier 3b `synthesized`** — fresh UUID, written to `cwd/.stoobz/.session-id`
2. **Pre-allocate scaffolding** (hard gate — exits 1 on failure):
   - `mkdir -p $SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/`
   - Create `.session-artifacts.json` with `{schema_version: 1, session_id, started_at, source_dir, artifacts: []}` if missing. **Never** rewrite an existing ledger.
3. **Extract `started_at` and `last_exchange`** from the resolved JSONL (tier 1/2 only — tier-3 leaves both null / current-time). The JSONL path is pinned to `~/.claude/projects/<encoded>/<session_id>.jsonl`; never globbed. `last_exchange` filters to **real user entries** only: `type==user` AND `isMeta!=true` AND `isSidechain!=true` AND content is a string OR an array whose first element has `type==text`. Text is truncated at 80 chars with `...`.
4. **Atomic manifest read-modify-write** under exclusive file lock (filelock library, sidecar `.lock` file):
   - First check-in (no entry for this `session_id`): append a fresh entry with the full schema.
   - Re-entry: refresh `last_activity` (always) and `last_exchange` (when extraction yields a value); dedupe-append to `skills_used` per mode. Never rewrite `id`, `session_id`, `started_at`, `source_dir`, `project`, `date`, or chain metadata.
5. **Emit** the appropriate message (or JSON if `--json`).

## Manifest entry schema (first check-in)

```json
{
  "id": "<session-uuid>",
  "project": "<basename of git toplevel or cwd>",
  "date": "<YYYY-MM-DD>",
  "label": null,
  "summary": null,
  "source_dir": "<absolute cwd>",
  "archive_path": null,
  "branch": "<git branch or null>",
  "artifacts": [],
  "tags": [],
  "type": "session",
  "status": "active",
  "session_id": "<session-uuid>",
  "return_to": "cd <cwd> && claude --resume <sid>",
  "chain_id": null,
  "chain_position": null,
  "previous_session_id": null,
  "parent_chain_id": null,
  "checkpoint_nodes": null,
  "started_at": "<ISO-8601 from first JSONL entry, or current time for tier-3>",
  "last_activity": "<ISO-8601 now>",
  "last_exchange": { "user": { "text": "...", "timestamp": "..." }, "assistant": { ... } },
  "skills_used": ["<skill-or-checkin-or-empty>"]
}
```

For tier-3 sessions: `return_to` is `null`, `last_exchange` is `null`, `branch` may be `null`.

## Ledger schema (initial; written once)

```json
{
  "schema_version": 1,
  "session_id": "<session-uuid>",
  "started_at": "<ISO-8601 — matches the manifest entry>",
  "source_dir": "<absolute cwd>",
  "artifacts": []
}
```

`schema_version`, `session_id`, `started_at`, `source_dir` are write-once. `artifacts` is append-only and is **owned by artifact-writing skills** under `write-artifact-protocol.md`. `/checkin` never touches `artifacts`.

## Skills That Invoke `/checkin`

All artifact-producing session-kit skills, as a silent precondition. Currently:

`park`, `pickup`, `persist`, `checkpoint`, `tldr`, `relay`, `hone`, `retro`, `handoff`, `rca`, `prime`

`sweep` (maintenance) and `index` (read-only query) do **not** invoke `/checkin` — they have no artifact to durably write.

## Chain Propagation

A **chain** is a logical work stream spanning multiple sessions connected via park/pickup. By default `/checkin` leaves chain metadata `null` at registration; `/park` resolves the chain name and writes a `<!-- session-kit-chain ... -->` block to the relay baton, and `/pickup` re-enters with `--inherit-chain-from <baton>` so the binary populates chain fields on first-checkin. See `park/SKILL.md`, `pickup/SKILL.md`, and the [Chain Inheritance](#chain-inheritance) section below.

## Chain Inheritance

Chain fields are **registration-time only**: the new flags below populate the manifest entry on first-checkin and are ignored on re-entry. Re-entry always preserves whatever chain metadata is already in the manifest. This matches the parked/picked-up lifecycle — chain identity is decided once when the session enters Session Kit, then carried forward unchanged.

| Flag | Field populated on first-checkin |
|------|----------------------------------|
| `--chain-id` | `chain_id` |
| `--previous-session-id` | `previous_session_id` |
| `--chain-position` | `chain_position` |
| `--parent-chain-id` | `parent_chain_id` |
| `--checkpoint-nodes` | `checkpoint_nodes` (parsed CSV → JSON array of ints) |
| `--inherit-chain-from <path>` | Bulk-populate by parsing the relay baton's chain block |

`--inherit-chain-from` opens the file at `<path>`, regex-extracts the first `<!-- session-kit-chain ... -->` block, and maps:

- `chain_id` → `chain_id`
- `session_id` → `previous_session_id` (the PARKED session whose baton is being picked up)
- `chain_position` + 1 → `chain_position` (the new session is the next link in the chain)
- `parent_chain_id` → `parent_chain_id` (passthrough; checkpoint-originated chains)
- `checkpoint_nodes` → `checkpoint_nodes` (passthrough; JSON array or CSV accepted in the block)

Missing path or missing chain block: silent fallthrough — first-checkin proceeds with chain fields null. This is not a usage error, so `/pickup` can invoke `--inherit-chain-from` unconditionally on the baton path.

Individual flags override `--inherit-chain-from`. The full authoritative reference is `sk checkin --help`.

## Rules

- Resolution chain order is fixed: tier 1 → 2 → 3. Higher tiers take precedence.
- The only conditions that abort the caller are: `mkdir -p` of active dir, ledger creation, manifest update. All three exit `1`. Everything else (JSONL miss, branch lookup miss, missing `last_exchange`) degrades gracefully.
- The active dir + ledger are scaffolding — created once, never modified. Liveness fields on the manifest entry refresh every call.
- Timestamps are ISO-8601 UTC with second precision and `Z` suffix (`2026-05-17T14:32:08Z`). No microseconds, no naive datetimes.
- The binary acquires an exclusive file lock around every manifest read-modify-write. Parallel Claude sessions sharing one manifest are safe.

## See also

- ADR-0005 (Skills as thin orchestrators of versioned scripts) — why this skill is a thin wrapper over a binary
- ADR-0004 (Session Kit artifact durability) — the durable-first protocol the binary encodes
- [write-artifact-protocol.md](../write-artifact-protocol.md) — the write contract artifact-emitting skills follow
- `sk checkin --help` — full arg, exit-code, env, and JSON-schema reference straight from the binary
