# Session Check-In Protocol

Early registration of active Claude Code sessions in the manifest, plus pre-allocation of the active archive directory and artifact ledger that the durable-first write protocol depends on (see [write-artifact-protocol.md](write-artifact-protocol.md)).

## How It Works

```
First skill invocation → detect session UUID
                       → create "active" manifest entry
                       → pre-allocate <session-id>-active/ dir + .session-artifacts.json ledger
Subsequent invocations → update last_activity, last_exchange, skills_used (idempotent on dir/ledger)
/park                  → upgrade entry to "archived", rename active dir to date-label
```

Entries without a `status` field are treated as `"archived"` (backward compatible with existing manifest entries).

## Session ID Resolution

Three-tier resolution chain — first tier to produce a non-empty `SESSION_ID` wins. All tiers are graceful; a missing tier falls through to the next. **Resolution failure is not a hard gate.**

```bash
# --- Tier 1: cwd-encoded JSONL ---
ENCODED="$(echo "$(pwd)" | tr '/' '-')"
SESSION_FILE="$(ls -t "$HOME/.claude/projects/${ENCODED}"/*.jsonl 2>/dev/null | head -1)"
SESSION_ID="$(basename "$SESSION_FILE" .jsonl 2>/dev/null)"
RESOLVED_VIA="jsonl"

# --- Tier 2: git-root-encoded JSONL ---
if [ -z "$SESSION_ID" ]; then
  GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -n "$GIT_ROOT" ]; then
    ENCODED="$(echo "$GIT_ROOT" | tr '/' '-')"
    SESSION_FILE="$(ls -t "$HOME/.claude/projects/${ENCODED}"/*.jsonl 2>/dev/null | head -1)"
    SESSION_ID="$(basename "$SESSION_FILE" .jsonl 2>/dev/null)"
    [ -n "$SESSION_ID" ] && RESOLVED_VIA="git-root"
  fi
fi

# --- Tier 3: cached or synthesized UUID in cwd/.stoobz/.session-id ---
if [ -z "$SESSION_ID" ]; then
  CACHE_FILE="./.stoobz/.session-id"
  if [ -f "$CACHE_FILE" ]; then
    SESSION_ID="$(cat "$CACHE_FILE" | tr -d '[:space:]')"
    RESOLVED_VIA="cached"
  fi
  if [ -z "$SESSION_ID" ]; then
    mkdir -p ./.stoobz
    SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
    printf '%s\n' "$SESSION_ID" > "$CACHE_FILE"
    RESOLVED_VIA="synthesized"
  fi
fi

# Build return_to with ~ for readability (omit for tier-3 sessions — there is no resume target)
if [ "$RESOLVED_VIA" = "jsonl" ] || [ "$RESOLVED_VIA" = "git-root" ]; then
  RETURN_TO="cd $(pwd | sed "s|^$HOME|~|") && claude --resume $SESSION_ID"
else
  RETURN_TO=null
fi
```

**Tier semantics:**

| Tier | Source | When it wins |
|------|--------|--------------|
| 1 — `jsonl` | Most recently modified `.jsonl` under `~/.claude/projects/<cwd-encoded>/` | Normal Claude Code session in any cwd Claude Code has tracked |
| 2 — `git-root` | Same lookup but against the git repo root's encoded path | Cwd is a subdir of a git repo Claude Code has tracked at the root |
| 3a — `cached` | Existing `cwd/.stoobz/.session-id` | Tier-3 already ran in this cwd; UUID was persisted |
| 3b — `synthesized` | New UUID written to `cwd/.stoobz/.session-id` | Scratch cwd (e.g. `/tmp`), empty repo, or otherwise outside Claude Code's tracking |

**No hard gate.** Session-ID resolution always succeeds — tier 3 is a last-resort UUID synthesis with idempotent caching. A scratch cwd or empty repo is a legitimate use case; refusing to write here was wrong (prior versions). The actual durability promise is upheld by archive-dir + ledger creation (see below); if either of those fails, *then* check-in aborts.

The cached `.stoobz/.session-id` file is a small text file (UUID + newline). `.stoobz/` is gitignored by convention so it does not pollute repos.

## Active Archive Directory + Ledger

The durable-first protocol requires that, by the time any artifact-writing skill runs, an active archive directory and an empty ledger already exist. Check-in is responsible for creating both.

**Active dir path:**

```
$SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/
```

`<project>` is `basename $(git rev-parse --show-toplevel)` or `basename $(pwd)` (same logic as the manifest entry's project field).

**Ledger path:** `<active-dir>/.session-artifacts.json`

**Initial ledger content:**

```json
{
  "schema_version": 1,
  "session_id": "<session-uuid>",
  "started_at": "<iso8601 — matches manifest entry>",
  "source_dir": "<absolute cwd path>",
  "artifacts": []
}
```

### Idempotency

Check-in runs on every session-kit skill invocation, but active-dir + ledger creation must be safe to re-enter:

- **Active dir:** `mkdir -p` — no-op if it already exists.
- **Ledger:** create only if missing. If a ledger already exists, leave it alone. The `session_id`, `started_at`, and `source_dir` fields are **write-once**; the `artifacts` array is **append-only** (skills append; nothing rewrites prior entries).

### The only hard gate: durability failure

If **`mkdir -p` of the active dir fails** OR **ledger creation fails** (permissions, disk full, read-only filesystem, etc.), check-in MUST abort the calling skill:

- Surface a clear error: which operation failed, against which path, and the underlying error message.
- **Do not** proceed to the skill's Process section. **Do not** write any artifact (not the archive, not cwd).
- The skill terminates here. The operator's path forward is to fix `~/.stoobz/` writability or override `$SESSION_KIT_ROOT`.

This is the **only** condition that aborts check-in. Session-ID resolution always succeeds (tier-3 fallback); manifest read failures recover gracefully (backup + recreate); JSONL extraction failures degrade fields to null. Fail-loud is reserved for the actual durability promise breaking — "we cannot write the artifact durably from here."

## Timestamp Extraction

**`started_at`:** Read the first JSONL entry's `timestamp` field via `head -1 "$SESSION_FILE"` and parse. Set once on initial registration, never updated.

**`last_exchange`:** Scan **backward** through the JSONL for the most recent **real** user entry and the most recent assistant entry. Truncate text at 80 chars, append `...` if truncated.

A "real" user entry is one that matches **all** of:

- `.type == "user"`
- `.isMeta != true` — excludes synthetic skill-launch injections (`/foo` slash-command preambles, "Base directory for this skill: …" loads)
- `.isSidechain != true` — excludes sub-agent and orchestration sidechains
- `.message.content` is a **string**, OR is an **array** whose first element has `.type == "text"` — excludes tool-result arrays (`.message.content[0].type == "tool_result"`)

Use the first match found scanning from the tail. The text payload is `.message.content` (string form) or `.message.content[0].text` (array form).

The most recent assistant entry is `.type == "assistant"` with `.message.content[0].text` (first text block; tool-use blocks are skipped).

Both extractions are best-effort — if no matching entry exists (very early in a session), set the field to `null`. This is not a hard-gate condition; the skill proceeds.

## Active Entry Schema

When a session is first registered, the manifest entry looks like:

```json
{
  "id": "<session-uuid>",
  "project": "<project-name>",
  "date": "<YYYY-MM-DD>",
  "label": null,
  "summary": null,
  "source_dir": "<absolute path to cwd>",
  "archive_path": null,
  "branch": "<git branch or null>",
  "artifacts": [],
  "tags": [],
  "type": "session",

  "status": "active",
  "session_id": "<session-uuid>",
  "return_to": "cd ~/path/to/project && claude --resume <session-uuid>",

  "chain_id": null,
  "chain_position": null,
  "previous_session_id": null,
  "parent_chain_id": null,
  "checkpoint_nodes": null,

  "started_at": "<ISO-8601 timestamp from first JSONL entry>",
  "last_activity": "<ISO-8601 timestamp, updated each check-in>",
  "last_exchange": {
    "user": {
      "text": "<truncated to 80 chars>...",
      "timestamp": "<ISO-8601>"
    },
    "assistant": {
      "text": "<truncated to 80 chars>...",
      "timestamp": "<ISO-8601>"
    }
  },
  "skills_used": ["<skill-name>"]
}
```

**Chain fields** on first registration: `chain_id`, `chain_position`, and `previous_session_id` are null unless `/pickup` inherited chain metadata from a relay baton (see Chain Propagation below). **Checkpoint fields** (`parent_chain_id`, `checkpoint_nodes`) are null unless the chain originated from `/checkpoint`.

## Check-In Process (executed by each skill)

### Initial Registration (no entry with this `session_id`)

1. **Resolve session ID** via the three-tier chain above. Always succeeds: tier 3 synthesizes a UUID and caches it in `cwd/.stoobz/.session-id` if tiers 1+2 miss.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create with `{"sessions": []}` if missing).
3. Determine project name: `basename $(git rev-parse --show-toplevel)` or `basename $(pwd)`. For tier-3 sessions in non-repo cwds, `basename $(pwd)` (e.g. `tmp` for `/tmp`).
4. Determine branch: `git branch --show-current` or null.
5. Extract `started_at` from first JSONL entry. For tier-3 sessions (no JSONL), use current ISO-8601 timestamp.
6. Extract `last_exchange` from JSONL using the filter in § Timestamp Extraction. For tier-3 sessions, set to `null`.
7. Create the active entry (schema above) with this skill in `skills_used`. For tier-3 sessions, `return_to` is `null` (no resume target).
8. Write manifest.
9. **Pre-allocate the active archive dir:** `mkdir -p $SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/`. **If this fails, abort the calling skill** (see § The only hard gate).
10. **Create the ledger** at `<active-dir>/.session-artifacts.json` with the initial content shown above (empty `artifacts: []`). Create-if-missing — if a ledger already exists, leave it alone. **If creation fails, abort the calling skill.**
11. Proceed to main skill process. No output about check-in.

### Update (entry with this `session_id` already exists)

1. Update `last_activity` to current ISO-8601 timestamp.
2. Update `last_exchange` from JSONL.
3. Append this skill name to `skills_used` (no duplicates).
4. Write manifest.
5. **Re-verify active dir + ledger.** If either is missing (manifest entry exists but archive prep didn't complete previously, e.g., crashed between steps 8 and 10), run the pre-allocation steps from Initial Registration. `mkdir -p` is idempotent; ledger creation is a "create if missing" no-op when present.
6. Proceed to main skill process. No output about check-in.

## Chain Propagation

A **chain** is a logical work stream spanning multiple Claude Code sessions connected via park/pickup.

### Chain Lifecycle

```
Session 11ce89e4 (stoobz-api dir)  →  /park  →  relay baton
  chain_id: "brrp-migration"                      |
  chain_position: 1                    CONTEXT_FOR_NEXT_SESSION.md
  previous_session_id: null            (includes chain metadata block)
                                               |
Session 25788ed2 (stoobz-web dir)  ←  /pickup inherits chain
  chain_id: "brrp-migration"
  chain_position: 2
  previous_session_id: "11ce89e4-..."
```

### Rules

1. **First session** (no prior context): `chain_id` = null on registration. `/park` sets `chain_id` to the park label (or `session_id` as fallback). `chain_position` = 1. `previous_session_id` = null.

2. **`/park` writes chain metadata** into `CONTEXT_FOR_NEXT_SESSION.md` as a machine-readable comment block:
   ```
   <!-- session-kit-chain
   chain_id: brrp-migration
   session_id: 25788ed2-e980-4150-bc0d-1e0cdac7388c
   chain_position: 2
   -->
   ```

3. **`/pickup` reads chain metadata** from the relay baton. During check-in registration, sets:
   - `chain_id` = inherited chain_id
   - `previous_session_id` = the session_id from the relay baton
   - `chain_position` = inherited chain_position + 1
   - `parent_chain_id` = inherited if present (checkpoint-originated chains)
   - `checkpoint_nodes` = inherited if present (checkpoint-originated chains)

4. **`/park` with label** on a position-1 session: if `chain_id` equals the `session_id` (fallback), update it to the park label so the chain gets a proper name.

5. **No chain metadata in relay baton** (legacy context or first session): start a new chain. `chain_id` set by `/park`.

6. **`/checkpoint` creates a branch chain** by writing extended chain metadata:
   ```
   <!-- session-kit-chain
   chain_id: brrp-migration-cp-2026-03-01
   session_id: 3a4b5c6d-...
   chain_position: 1
   parent_chain_id: brrp-migration
   checkpoint_nodes: 1,2,4
   -->
   ```
   The `parent_chain_id` and `checkpoint_nodes` fields are unique to checkpoint-originated chains. They create a DAG (directed acyclic graph) relationship between chains, visible via `/index --chain`.

### Chain Naming Resolution

Same as park label resolution — first match wins:
- Explicit `/park <label>` argument
- Git branch name (if not main/master/develop)
- Slugified TLDR heading
- Session ID as fallback

The first `/park` in a chain names it. Subsequent sessions inherit.

## Failure Modes

| Failure | Behavior |
|---------|----------|
| Tier-1 (jsonl) lookup misses | Fall through to tier 2. Not a failure. |
| Tier-2 (git-root) lookup misses | Fall through to tier 3. Not a failure. |
| Tier-3 cache file unreadable | Synthesize a fresh UUID, overwrite the cache. |
| Active dir `mkdir -p` fails | **Fail loudly.** Abort the calling skill. Real durability failure. |
| Ledger creation fails | **Fail loudly.** Abort the calling skill. Real durability failure. |
| Manifest read fails | Back up as `.bak`, create fresh, register. |
| JSONL read fails (timestamps/exchange) | Use current time for `started_at`, null for `last_exchange`. |
| Chain metadata missing from relay | Start new chain (null chain fields). |
| Checkpoint metadata missing from relay | Normal chain (null parent_chain_id, null checkpoint_nodes). |

Fail-loud is reserved exclusively for the two rows that mean **"can't durably write."** Session-ID resolution is no longer a failure mode — tier-3 synthesis always produces an ID. The lazy-archive era's "skip silently" was wrong; the brief "fail loudly on any miss" was over-correction. The correct gate is the one tied to the durability promise the architecture is actually making.

## Skills That Check In

All session-kit skills except `sweep` (maintenance) and `index` (read-only query):

`park`, `pickup`, `persist`, `checkpoint`, `tldr`, `relay`, `hone`, `retro`, `handoff`, `rca`, `prime`

## Skills Tracking

The `skills_used` array tracks **all** skills invoked during the session, not just domain skills. This includes session-kit skills. No duplicates — each skill name appears at most once. The skill name is the value from the SKILL.md frontmatter `name` field.
