# Session Check-In Protocol

Early registration of active Claude Code sessions in the manifest. Makes live sessions discoverable via `/index --active` even if the terminal crashes before `/park`.

## How It Works

```
First skill invocation → detect session UUID → create "active" manifest entry
Subsequent invocations → update last_activity, last_exchange, skills_used
/park                  → upgrade entry to "archived" with full metadata
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

If detection fails, skip check-in silently. The skill proceeds normally.

## Timestamp Extraction

**`started_at`:** Read the first JSONL entry's `timestamp` field via `head -1 "$SESSION_FILE"` and parse. Set once on initial registration, never updated.

**`last_exchange`:** Read the last user + assistant entries from the `.jsonl` via `tail` + reverse parse. Truncate text at 80 chars, append `...` if truncated.

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

**Chain fields** on first registration: `chain_id`, `chain_position`, and `previous_session_id` are null unless `/pickup` inherited chain metadata from a relay baton (see Chain Propagation below).

## Check-In Process (executed by each skill)

### Initial Registration (no entry with this `session_id`)

1. Detect session ID using the method above. If detection fails, skip silently.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create with `{"sessions": []}` if missing).
3. Determine project name: `basename $(git rev-parse --show-toplevel)` or `basename $(pwd)`.
4. Determine branch: `git branch --show-current` or null.
5. Extract `started_at` from first JSONL entry.
6. Extract `last_exchange` from last user + assistant JSONL entries.
7. Create the active entry (schema above) with this skill in `skills_used`.
8. Write manifest. Proceed to main skill process. No output about check-in.

### Update (entry with this `session_id` already exists)

1. Update `last_activity` to current ISO-8601 timestamp.
2. Update `last_exchange` from JSONL.
3. Append this skill name to `skills_used` (no duplicates).
4. Write manifest. Proceed to main skill process. No output about check-in.

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

4. **`/park` with label** on a position-1 session: if `chain_id` equals the `session_id` (fallback), update it to the park label so the chain gets a proper name.

5. **No chain metadata in relay baton** (legacy context or first session): start a new chain. `chain_id` set by `/park`.

### Chain Naming Resolution

Same as park label resolution — first match wins:
- Explicit `/park <label>` argument
- Git branch name (if not main/master/develop)
- Slugified TLDR heading
- Session ID as fallback

The first `/park` in a chain names it. Subsequent sessions inherit.

## Graceful Degradation

| Failure | Behavior |
|---------|----------|
| Session ID detection fails | Skip check-in, skill proceeds normally |
| Manifest read fails | Back up as `.bak`, create fresh, register |
| JSONL read fails (timestamps/exchange) | Use current time for `started_at`, null for `last_exchange` |
| Chain metadata missing from relay | Start new chain (null chain fields) |

## Skills That Check In

All session-kit skills except `sweep` (maintenance) and `index` (read-only query):

`park`, `pickup`, `persist`, `tldr`, `relay`, `hone`, `retro`, `handoff`, `rca`, `prime`

## Skills Tracking

The `skills_used` array tracks **all** skills invoked during the session, not just domain skills. This includes session-kit skills. No duplicates — each skill name appears at most once. The skill name is the value from the SKILL.md frontmatter `name` field.
