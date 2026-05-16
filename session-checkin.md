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

## Session ID Detection

The current session's `.jsonl` is the most recently modified file in its project directory:

```bash
# Encode cwd to match Claude Code's project dir naming (/ → -)
ENCODED="$(echo "$(pwd)" | tr '/' '-')"

# Most recently modified .jsonl = active session
SESSION_FILE="$(ls -t "$HOME/.claude/projects/${ENCODED}"/*.jsonl 2>/dev/null | head -1)"
SESSION_ID="$(basename "$SESSION_FILE" .jsonl 2>/dev/null)"

# Fallback: try git root encoding
if [ -z "$SESSION_ID" ]; then
  GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -n "$GIT_ROOT" ]; then
    ENCODED="$(echo "$GIT_ROOT" | tr '/' '-')"
    SESSION_FILE="$(ls -t "$HOME/.claude/projects/${ENCODED}"/*.jsonl 2>/dev/null | head -1)"
    SESSION_ID="$(basename "$SESSION_FILE" .jsonl 2>/dev/null)"
  fi
fi

# Build return_to with ~ for readability
RETURN_TO="cd $(pwd | sed "s|^$HOME|~|") && claude --resume $SESSION_ID"
```

**Failure policy (changed from prior versions).** If both the cwd-encoded lookup and the git-root fallback fail to produce a `SESSION_ID`, **check-in MUST abort the calling skill**.

This is a hard gate, not an advisory:

- Surface the error message from [write-artifact-protocol.md § Session-ID detection failure](write-artifact-protocol.md) to the operator.
- **Do not** proceed to the skill's Process section. **Do not** write any artifact anywhere (not the archive, not cwd). **Do not** silently degrade.
- The skill terminates here. The operator's only options are (a) move to a Claude-Code-tracked cwd / git repo, or (b) set `SESSION_KIT_SESSION_ID` and retry.

The prior "skip silently" policy was safe under lazy-archive (artifacts went to cwd regardless), but under durable-first it would mask a real failure mode — the artifact would be written to cwd only, with no archive copy and no ledger entry. That is the exact outcome ADR-0004 set out to eliminate.

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

If the active dir or ledger creation fails (permissions, disk, etc.), **check-in MUST abort the calling skill** with the same hard-gate semantics as session-ID detection failure above. Without an active dir + ledger, no artifact can be written durably; lazy fallback is not an option.

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

1. Detect session ID using the method above. If both detection paths fail, **fail loudly** (see Failure policy above).
2. Read `$SESSION_KIT_ROOT/manifest.json` (create with `{"sessions": []}` if missing).
3. Determine project name: `basename $(git rev-parse --show-toplevel)` or `basename $(pwd)`.
4. Determine branch: `git branch --show-current` or null.
5. Extract `started_at` from first JSONL entry.
6. Extract `last_exchange` from last user + assistant JSONL entries.
7. Create the active entry (schema above) with this skill in `skills_used`.
8. Write manifest.
9. **Pre-allocate the active archive dir:** `mkdir -p $SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/`. If this fails, fail loudly.
10. **Create the ledger** at `<active-dir>/.session-artifacts.json` with the initial content shown above (empty `artifacts: []`). If a ledger already exists at this path, leave it alone (idempotent — see below).
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
| Session ID detection fails (both .jsonl + git-root) | **Fail loudly.** Refuse to proceed; surface message from [write-artifact-protocol.md](write-artifact-protocol.md). |
| Active dir `mkdir -p` fails | **Fail loudly.** Durable-first protocol cannot run without it. |
| Ledger creation fails | **Fail loudly.** Same reason. |
| Manifest read fails | Back up as `.bak`, create fresh, register. |
| JSONL read fails (timestamps/exchange) | Use current time for `started_at`, null for `last_exchange`. |
| Chain metadata missing from relay | Start new chain (null chain fields). |
| Checkpoint metadata missing from relay | Normal chain (null parent_chain_id, null checkpoint_nodes). |

The shift from "graceful degradation" to "fail loudly" on the first three rows is deliberate: lazy-archive could afford best-effort check-in because artifacts went to cwd regardless. Durable-first cannot — if check-in fails, the artifact has nowhere to land.

## Skills That Check In

All session-kit skills except `sweep` (maintenance) and `index` (read-only query):

`park`, `pickup`, `persist`, `checkpoint`, `tldr`, `relay`, `hone`, `retro`, `handoff`, `rca`, `prime`

## Skills Tracking

The `skills_used` array tracks **all** skills invoked during the session, not just domain skills. This includes session-kit skills. No duplicates — each skill name appears at most once. The skill name is the value from the SKILL.md frontmatter `name` field.
