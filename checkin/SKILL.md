---
name: checkin
description: Register the current Claude Code session under Session Kit and pre-allocate the durable archive + ledger that other session-kit skills depend on. Use when the user says "/checkin", "register this session", "set up session kit here", "start a session", or starts working in a scratch / unfilled cwd and wants explicit Session Kit affordances before any artifact-writing skill fires. Also invoked silently as a precondition by every other artifact-producing session-kit skill (tldr, relay, hone, retro, handoff, rca, persist, park, pickup, checkpoint, prime).
---

# Check-In

Ensure the current session is registered in `$SESSION_KIT_ROOT/manifest.json` with a resolved session ID, and that the durable archive directory + artifact ledger exist. Idempotent on re-entry — once set up, subsequent invocations are no-ops.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Two Modes

`/checkin` runs the same scaffolding + liveness-refresh ceremony in both modes. Two things differ: console output, and whether `"checkin"` is appended to `skills_used`.

| Mode | Trigger | Output on first check-in | Output on re-entry | Output on durability failure | Appends `"checkin"` to `skills_used`? |
|------|---------|--------------------------|---------------------|------------------------------|----------------------------------------|
| **Explicit** | User invokes `/checkin` (slash-command) | `Session checked in: <session-id> → <archive-path>; ledger initialized (resolved via <tier>)` | `Already checked in: <session-id>` | Abort with error message | **Yes** — operator deliberately ran the skill |
| **Silent** | Another session-kit skill invokes as a precondition | None | None | Abort the calling skill with error message | **No** — the invoking skill owns its own entry |

**How to distinguish:** if the immediate trigger is a user typing `/checkin`, use explicit mode. If another skill's prose says "invoke `/checkin` (silent) as a precondition" or equivalent, use silent mode. Both modes execute the same protocol; the user-facing differences are exactly the two columns above.

## Execution Discipline

**The entire ceremony — resolution + scaffolding + manifest update + output — MUST run inside a single bash invocation.** Claude Code's `Bash` tool spawns a fresh shell for each call; variables set in one call (`SESSION_ID`, `ACTIVE_DIR`, `SESSION_FILE`, `NOW`, etc.) are gone in the next. Splitting the protocol across multiple `Bash` calls is the most common way this skill regresses — half-empty paths get `mkdir`'d, ledgers get created with the wrong `session_id`, mirrors copy from nonexistent sources.

The Process section below describes the steps as prose for clarity. The canonical implementation is the single bash block in [Reference Implementation](#reference-implementation) at the end of this skill; treat it as the executable specification. If you must improvise, bundle every shell step into one heredoc.

**Cross-platform note.** Pin every `date` invocation to `+"%Y-%m-%dT%H:%M:%SZ"` (no `%N` / no sub-second). BSD `date` on macOS does not understand `%N`; a format string like `+"%Y-%m-%dT%H:%M:%S.%3NZ"` produces literal `%3N` in the output. Drop sub-second precision.

## Session ID Resolution

Three-tier resolution chain — first tier to produce a non-empty `SESSION_ID` wins. All tiers are graceful; a missing tier falls through to the next. **Resolution failure is not a hard gate.**

> **Illustrative only.** The snippet below shows just the resolution step in isolation, for clarity. **Do not** run it as a standalone bash invocation — see [Execution Discipline](#execution-discipline). The integrated implementation is in [Reference Implementation](#reference-implementation).

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

if [ "$RESOLVED_VIA" = "jsonl" ] || [ "$RESOLVED_VIA" = "git-root" ]; then
  RETURN_TO="cd $(pwd | sed "s|^$HOME|~|") && claude --resume $SESSION_ID"
else
  RETURN_TO=null
fi
```

| Tier | Source | When it wins |
|------|--------|--------------|
| 1 — `jsonl` | Most recently modified `.jsonl` under `~/.claude/projects/<cwd-encoded>/` | Normal Claude Code session in a tracked cwd |
| 2 — `git-root` | Same lookup against the git repo root's encoded path | Cwd is a subdir of a tracked git repo |
| 3a — `cached` | Existing `cwd/.stoobz/.session-id` | Tier-3 already ran here; UUID was persisted |
| 3b — `synthesized` | New UUID written to `cwd/.stoobz/.session-id` | Scratch cwd (e.g. `/tmp`), empty repo, or outside Claude Code's tracking |

`.stoobz/` is gitignored by convention, so the cache file does not pollute repos.

## Process

The prose below describes the same ceremony as [Reference Implementation](#reference-implementation), step by step. Treat the bash block as the canonical implementation; the prose is for orientation.

After resolving `SESSION_ID`:

1. Read `$SESSION_KIT_ROOT/manifest.json` (create with `{"sessions": []}` if missing).
2. Compute `ACTIVE_DIR = $SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/` where `<project>` is `basename $(git rev-parse --show-toplevel)` or `basename $(pwd)` (e.g. `tmp` for `/tmp`).
3. **Determine entry state.** Let `is_first_checkin = true` if any of these is missing for the resolved `SESSION_ID`: a manifest entry, `ACTIVE_DIR`, `$ACTIVE_DIR/.session-artifacts.json`. Otherwise `is_first_checkin = false` (re-entry).
4. **Ensure durable scaffolding** (always run; the underlying ops are create-if-missing and idempotent):
   - `mkdir -p $ACTIVE_DIR`. If this fails, abort with a durability-failure error (see Failure Modes).
   - If `$ACTIVE_DIR/.session-artifacts.json` does not exist, create it with the initial ledger content shown below. If creation fails, abort with a durability-failure error. **Never** rewrite or modify an existing ledger.
5. **Update the manifest entry:**
   - **First check-in:** create the entry (schema below). Fill `started_at` and `last_exchange` from the JSONL when available (tier 1 / tier 2); fall back to current time and `null` respectively for tier-3 sessions. Set `last_activity` to the current ISO-8601 UTC timestamp. Initialize `skills_used` per the rule in step 6.
   - **Re-entry:** refresh liveness on the existing entry. Set `last_activity` to the current ISO-8601 UTC timestamp. If `last_exchange` extraction yields a non-null value, overwrite the existing `last_exchange`; if it yields null (tier-3, or no real user entry yet), leave the existing value untouched. **Never** rewrite `started_at`, `session_id`, `source_dir`, or `id`.
6. **Append to `skills_used`** (no duplicates):
   - **Silent mode** (invoked as precondition by another skill): do **not** append `"checkin"`. The invoking skill is responsible for its own `skills_used` entry; check-in is a precondition, not a user-facing step.
   - **Explicit mode** (user typed `/checkin` directly): append `"checkin"`. The operator deliberately ran it as a skill; that's a real entry in the session's skill history.
7. Write the manifest.
8. Emit the appropriate message for the current mode:
   - First check-in, explicit: `Session checked in: <session-id> → <archive-path>; ledger initialized (resolved via <tier>)`
   - Re-entry, explicit: `Already checked in: <session-id>`
   - Silent (either branch): no output.

### Initial ledger content

```json
{
  "schema_version": 1,
  "session_id": "<session-uuid>",
  "started_at": "<iso8601 — matches manifest entry>",
  "source_dir": "<absolute cwd path>",
  "artifacts": []
}
```

The `session_id`, `started_at`, and `source_dir` fields are **write-once**. The `artifacts` array is **append-only** (added to by artifact-writing skills under [write-artifact-protocol.md](../write-artifact-protocol.md); never modified by `/checkin`).

### Active manifest entry schema

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

  "started_at": "<ISO-8601 timestamp from first JSONL entry, or current time for tier-3>",
  "last_activity": "<ISO-8601 timestamp at registration>",
  "last_exchange": {
    "user": {"text": "<truncated to 80 chars>...", "timestamp": "<ISO-8601>"},
    "assistant": {"text": "<truncated to 80 chars>...", "timestamp": "<ISO-8601>"}
  },
  "skills_used": ["<skill-name>"]
}
```

For tier-3 sessions: `return_to` is `null`, `last_exchange` is `null`, `started_at` is current ISO-8601, `branch` is null when no git repo.

### Timestamp / exchange extraction (tier-1 and tier-2 only)

**Pinned JSONL path.** All extraction MUST read from the specific session-scoped file:

```
$SESSION_FILE = $HOME/.claude/projects/$ENCODED/${SESSION_ID}.jsonl
```

Never glob `~/.claude/projects/$ENCODED/*.jsonl` for extraction — that can pick up an old or unrelated session's entries (a recent smoke test surfaced a 12-day-old exchange that way). The `SESSION_ID` already names the exact file the resolution chain located.

For tier-3 sessions `$SESSION_FILE` is unset; skip extraction (`started_at` ← `$NOW`, `last_exchange` ← `null`).

**Timestamp format.** Every ISO-8601 stamp uses `date -u +"%Y-%m-%dT%H:%M:%SZ"` — second precision, UTC, `Z` suffix. No `%N`, no sub-second. BSD `date` (macOS default) does not implement `%N` and silently emits the literal characters.

**`started_at`:** First JSONL entry's `timestamp` field via `head -1 "$SESSION_FILE"` and parse. Write once; never updated.

**`last_exchange`:** Scan **backward** through `$SESSION_FILE` for the most recent **real** user entry and the most recent assistant entry. Truncate text at 80 chars, append `...` if truncated.

A "real" user entry is one that matches **all** of:

- `.type == "user"`
- `.isMeta != true` — excludes synthetic skill-launch injections (`/foo` slash-command preambles, "Base directory for this skill: …" loads)
- `.isSidechain != true` — excludes sub-agent and orchestration sidechains
- `.message.content` is a **string**, OR is an **array** whose first element has `.type == "text"` — excludes tool-result arrays (`.message.content[0].type == "tool_result"`)

Use the first match found scanning from the tail. Text payload is `.message.content` (string form) or `.message.content[0].text` (array form).

The most recent assistant entry is `.type == "assistant"` with `.message.content[0].text` (first text block; tool-use blocks are skipped).

Best-effort — if no matching entry exists, set the field to `null`. Not a hard-gate condition.

## Scaffolding Idempotency, Liveness Refresh

`/checkin` is **scaffolding-idempotent** — it never re-creates or modifies the durable infrastructure once it exists. But it **refreshes liveness** on every invocation, so the manifest stays accurate as a "what's happening now" picture.

### Refresh on every check-in (silent or explicit)

| Field | When refreshed |
|-------|----------------|
| `last_activity` | **Always.** Set to current ISO-8601 UTC. |
| `last_exchange` | **When extraction yields a value.** Tier-3 sessions and sessions with no real user entry yet leave the existing value untouched (null on first check-in; null or stale on re-entry). |

### Append on every check-in, mode-dependent

| Field | Silent mode | Explicit mode |
|-------|-------------|---------------|
| `skills_used` | Do **not** append `"checkin"`. If `INVOKING_SKILL` is set in the environment, append that value (deduplicated). | Append `"checkin"` (deduplicated). The operator deliberately invoked it. |

**`INVOKING_SKILL` env-var contract.** A session-kit skill that invokes `/checkin` as a silent precondition exports `INVOKING_SKILL=<its frontmatter name>` first. `/checkin` reads that variable and records it in `skills_used` on the invoking skill's behalf. This centralizes manifest writes in `/checkin` — no other skill rewrites `skills_used`. Example: `/tldr` sets `INVOKING_SKILL=tldr`; `/relay` sets `INVOKING_SKILL=relay`; etc.

If both `MODE=explicit` and `INVOKING_SKILL=foo` are set (unusual, e.g. user types `/checkin` from inside another skill's flow), `/checkin` appends `"checkin"` only; `INVOKING_SKILL` is ignored. Explicit user invocation takes precedence.

### Never touched on re-entry

These are write-once or owned by other actors:

- **Active dir** (`mkdir -p` only — no recursion, no chmod, no reset)
- **Ledger file** (`.session-artifacts.json` — create-if-missing only)
- **Ledger write-once metadata:** `schema_version`, `session_id`, `started_at`, `source_dir`
- **Ledger `artifacts[]` array:** owned exclusively by artifact-writing skills under [write-artifact-protocol.md](../write-artifact-protocol.md)
- **Manifest write-once fields:** `id`, `session_id`, `started_at`, `source_dir`, `project`, `date`, chain metadata (managed by `/park` / `/pickup` / `/checkpoint`)

The re-entry user-facing message stays a clean `Already checked in: <session-id>`. The liveness refresh happens underneath — visible only to readers of the manifest (e.g. `/index --active`).

## Failure Modes

| Failure | Behavior |
|---------|----------|
| Tier-1 (jsonl) miss | Fall through to tier 2. Not a failure. |
| Tier-2 (git-root) miss | Fall through to tier 3. Not a failure. |
| Tier-3 cache unreadable | Synthesize a fresh UUID, overwrite the cache. |
| `mkdir -p` of active dir fails | **Abort.** Surface the path and underlying error. Real durability failure. |
| Ledger creation fails | **Abort.** Surface the path and underlying error. Real durability failure. |
| Manifest read fails | Back up as `.bak`, create fresh, continue. |
| JSONL read fails (tiers 1/2) | `started_at` ← current time, `last_exchange` ← null. |
| `last_exchange` has no matching real user entry | Set to `null`. Not a failure. |

Fail-loud is reserved exclusively for the two `Abort` rows. They are the only conditions that mean "cannot durably write the artifact."

## Chain Propagation

A **chain** is a logical work stream spanning multiple Claude Code sessions connected via park/pickup.

```
Session 11ce89e4 (some cwd)        →  /park  →  relay baton (CONTEXT_FOR_NEXT_SESSION.md)
  chain_id: "brrp-migration"                       (includes chain metadata block)
  chain_position: 1                                            |
  previous_session_id: null                                    |
                                                               v
Session 25788ed2 (different cwd)   ←  /pickup inherits chain
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
   The `parent_chain_id` and `checkpoint_nodes` fields are unique to checkpoint-originated chains. They create a DAG relationship between chains, visible via `/index --chain`.

### Chain Naming Resolution

Same as park label resolution — first match wins:
- Explicit `/park <label>` argument
- Git branch name (if not main/master/develop)
- Slugified TLDR heading
- Session ID as fallback

The first `/park` in a chain names it. Subsequent sessions inherit.

## Skills That Invoke `/checkin`

All artifact-producing session-kit skills, as a silent precondition. Currently:

`park`, `pickup`, `persist`, `checkpoint`, `tldr`, `relay`, `hone`, `retro`, `handoff`, `rca`, `prime`

`sweep` (maintenance) and `index` (read-only query) do **not** invoke `/checkin` — they have no artifact to durably write.

## Rules

- Resolution chain order is fixed: tier 1 → 2 → 3. Higher tiers take precedence; tier-3 is consulted only as last resort.
- Tier-3 cache (`cwd/.stoobz/.session-id`) is one UUID per cwd. If you delete it, the next `/checkin` synthesizes a new UUID and creates a new manifest entry — the previous tier-3 session becomes an orphan in the archive.
- The only conditions that abort the skill are active-dir `mkdir` failure and ledger creation failure.
- Re-invocation is **scaffolding-idempotent**: active dir and ledger are create-if-missing only; ledger write-once metadata and `artifacts[]` are never touched. But the manifest's liveness fields (`last_activity`, `last_exchange`) are refreshed every call. Re-entry message stays a clean `Already checked in: <session-id>`.
- `skills_used` append rule is mode-dependent: explicit mode appends `"checkin"`, silent mode does not.
- Silent mode emits no console output on success or re-entry; it emits the abort error only when durability fails. Explicit mode emits the success-on-first-run or re-entry message.
- All shell work happens in a single `Bash` invocation. See [Execution Discipline](#execution-discipline) and [Reference Implementation](#reference-implementation).
- Timestamps use `date -u +"%Y-%m-%dT%H:%M:%SZ"` (no `%N`). Last-exchange extraction reads only `$HOME/.claude/projects/$ENCODED/${SESSION_ID}.jsonl` — never a glob.

## Reference Implementation

The canonical implementation of the full ceremony. Run as a single `Bash` tool invocation. `MODE` is `"explicit"` when the user typed `/checkin`, `"silent"` when called from another skill's boilerplate.

```bash
#!/usr/bin/env bash
# /checkin — durable-first session registration + scaffolding + liveness refresh.
# MUST run as a single bash invocation; shell vars do not persist across calls.

set -euo pipefail
MODE="${MODE:-silent}"  # "explicit" or "silent"
SESSION_KIT_ROOT="${SESSION_KIT_ROOT:-$HOME/.stoobz}"
NOW="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
CWD="$(pwd)"

# === Tier resolution ===
ENCODED="$(echo "$CWD" | tr '/' '-')"
SESSION_ID=""
SESSION_FILE=""
RESOLVED_VIA=""

# Tier 1: cwd-encoded
CANDIDATE="$(ls -t "$HOME/.claude/projects/${ENCODED}"/*.jsonl 2>/dev/null | head -1 || true)"
if [ -n "$CANDIDATE" ]; then
  SESSION_ID="$(basename "$CANDIDATE" .jsonl)"
  SESSION_FILE="$HOME/.claude/projects/${ENCODED}/${SESSION_ID}.jsonl"
  RESOLVED_VIA="jsonl"
fi

# Tier 2: git-root-encoded
if [ -z "$SESSION_ID" ]; then
  GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$GIT_ROOT" ]; then
    ENCODED="$(echo "$GIT_ROOT" | tr '/' '-')"
    CANDIDATE="$(ls -t "$HOME/.claude/projects/${ENCODED}"/*.jsonl 2>/dev/null | head -1 || true)"
    if [ -n "$CANDIDATE" ]; then
      SESSION_ID="$(basename "$CANDIDATE" .jsonl)"
      SESSION_FILE="$HOME/.claude/projects/${ENCODED}/${SESSION_ID}.jsonl"
      RESOLVED_VIA="git-root"
    fi
  fi
fi

# Tier 3: cached UUID, else synthesize
if [ -z "$SESSION_ID" ]; then
  mkdir -p "$CWD/.stoobz"
  CACHE="$CWD/.stoobz/.session-id"
  if [ -f "$CACHE" ]; then
    SESSION_ID="$(tr -d '[:space:]' < "$CACHE")"
    RESOLVED_VIA="cached"
  fi
  if [ -z "$SESSION_ID" ]; then
    SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
    printf '%s\n' "$SESSION_ID" > "$CACHE"
    RESOLVED_VIA="synthesized"
  fi
fi

# === Derived paths ===
PROJECT="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo "$CWD")")"
ACTIVE_DIR="$SESSION_KIT_ROOT/sessions/$PROJECT/${SESSION_ID}-active"
LEDGER="$ACTIVE_DIR/.session-artifacts.json"
MANIFEST="$SESSION_KIT_ROOT/manifest.json"

# === Hard gate: scaffolding ===
mkdir -p "$SESSION_KIT_ROOT"
[ -f "$MANIFEST" ] || echo '{"sessions": []}' > "$MANIFEST"

if ! mkdir -p "$ACTIVE_DIR" 2>/tmp/sk-mkdir.err; then
  echo "abort: mkdir failed at $ACTIVE_DIR: $(cat /tmp/sk-mkdir.err)" >&2
  exit 1
fi

if [ ! -f "$LEDGER" ]; then
  # Pull started_at from JSONL if available; else NOW.
  STARTED_AT="$NOW"
  if [ -n "$SESSION_FILE" ] && [ -f "$SESSION_FILE" ]; then
    FIRST_TS="$(head -1 "$SESSION_FILE" | jq -r '.timestamp // empty' 2>/dev/null || true)"
    [ -n "$FIRST_TS" ] && STARTED_AT="$FIRST_TS"
  fi
  if ! jq -n --arg sid "$SESSION_ID" --arg sa "$STARTED_AT" --arg src "$CWD" '
    {schema_version: 1, session_id: $sid, started_at: $sa, source_dir: $src, artifacts: []}
  ' > "$LEDGER" 2>/tmp/sk-ledger.err; then
    echo "abort: ledger creation failed at $LEDGER: $(cat /tmp/sk-ledger.err)" >&2
    exit 1
  fi
fi

# === Extract last_exchange (tier-1/2 only) ===
LAST_EXCHANGE='null'
if [ -n "$SESSION_FILE" ] && [ -f "$SESSION_FILE" ]; then
  LAST_EXCHANGE="$(jq -s --arg now "$NOW" '
    # Real user entries: user role, not isMeta, not isSidechain, content is string or text-array
    def real_user: .type == "user"
      and (.isMeta // false) != true
      and (.isSidechain // false) != true
      and ((.message.content | type) == "string"
           or ((.message.content | type) == "array" and (.message.content[0].type // "") == "text"));
    def text_of_user: if (.message.content | type) == "string"
                       then .message.content
                       else (.message.content[0].text // "") end;
    def trunc: if (length > 80) then (.[0:80] + "...") else . end;

    (map(select(real_user)) | last) as $u
    | (map(select(.type == "assistant")) | last) as $a
    | if ($u == null and $a == null) then null
      else {
        user: (if $u == null then null else {
                 text: ($u | text_of_user | trunc),
                 timestamp: ($u.timestamp // null)
               } end),
        assistant: (if $a == null then null else {
                      text: ($a.message.content[0].text // "" | trunc),
                      timestamp: ($a.timestamp // null)
                    } end)
      }
      end
  ' "$SESSION_FILE" 2>/dev/null || echo null)"
fi

# === Determine first-checkin vs re-entry ===
IS_FIRST="$(jq --arg sid "$SESSION_ID" '
  [.sessions[] | select(.session_id == $sid)] | length == 0
' "$MANIFEST")"

# === Branch project name and branch for first-checkin path ===
BRANCH="$(git branch --show-current 2>/dev/null || true)"
[ -z "$BRANCH" ] && BRANCH=null || BRANCH="\"$BRANCH\""

# === Compute return_to ===
if [ "$RESOLVED_VIA" = "jsonl" ] || [ "$RESOLVED_VIA" = "git-root" ]; then
  RETURN_TO="cd $(echo "$CWD" | sed "s|^$HOME|~|") && claude --resume $SESSION_ID"
  RETURN_TO_JSON="\"$RETURN_TO\""
else
  RETURN_TO_JSON=null
fi

# === Update manifest ===
# Append-or-update single entry; refresh liveness; conditional skills_used append.
# Precedence: MODE=explicit → "checkin"; else INVOKING_SKILL if set; else no append.
APPEND_SKILL=""
if [ "$MODE" = "explicit" ]; then
  APPEND_SKILL="checkin"
elif [ -n "${INVOKING_SKILL:-}" ]; then
  APPEND_SKILL="$INVOKING_SKILL"
fi

TMP_MANIFEST="$(mktemp)"
jq \
  --arg sid "$SESSION_ID" \
  --arg now "$NOW" \
  --arg project "$PROJECT" \
  --arg src "$CWD" \
  --arg active_dir "$ACTIVE_DIR" \
  --arg resolved_via "$RESOLVED_VIA" \
  --arg append_skill "$APPEND_SKILL" \
  --argjson last_exchange "$LAST_EXCHANGE" \
  --argjson return_to "$RETURN_TO_JSON" \
  --argjson is_first "$IS_FIRST" \
  '
  def refresh_liveness:
    .last_activity = $now
    | (if $last_exchange != null then .last_exchange = $last_exchange else . end)
    | (if $append_skill != "" then .skills_used = ((.skills_used // []) + [$append_skill] | unique) else . end);

  if $is_first then
    .sessions += [{
      id: $sid, project: $project, date: ($now[0:10]),
      label: null, summary: null,
      source_dir: $src, archive_path: null, branch: null,
      artifacts: [], tags: [], type: "session",
      status: "active", session_id: $sid, return_to: $return_to,
      chain_id: null, chain_position: null, previous_session_id: null,
      parent_chain_id: null, checkpoint_nodes: null,
      started_at: $now,
      last_activity: $now,
      last_exchange: $last_exchange,
      skills_used: (if $append_skill != "" then [$append_skill] else [] end)
    }]
  else
    .sessions = (.sessions | map(if .session_id == $sid then refresh_liveness else . end))
  end
  ' "$MANIFEST" > "$TMP_MANIFEST" && mv "$TMP_MANIFEST" "$MANIFEST"

# === Output ===
if [ "$MODE" = "explicit" ]; then
  if [ "$IS_FIRST" = "true" ]; then
    echo "Session checked in: $SESSION_ID → $ACTIVE_DIR; ledger initialized (resolved via $RESOLVED_VIA)"
  else
    echo "Already checked in: $SESSION_ID"
  fi
fi

# Export for downstream skill bundling (when /checkin is invoked inline as part of another skill's bash block, these are already in scope).
export SESSION_ID SESSION_FILE RESOLVED_VIA ACTIVE_DIR LEDGER MANIFEST PROJECT NOW
```

A skill invoking `/checkin` silently as a precondition can either:

1. Invoke this entire block via the `Skill` tool (separate bash process; only the manifest/scaffolding side-effects persist), then re-derive `ACTIVE_DIR` etc. at the start of its own bash block; OR
2. Inline this block at the top of its own bundled bash invocation, then continue with the artifact write — the exported variables stay in scope.

Approach (2) is preferred for skills that need `$ACTIVE_DIR` for the write step (essentially all of them — see [tldr/SKILL.md](../tldr/SKILL.md) for a worked example).
