---
name: index
description: Scan $SESSION_KIT_ROOT/manifest.json (default ~/.stoobz/) for session artifacts and build a searchable index of past work. Use when the user says "/index", "find that session", "list my sessions", "what did I work on", "where was that investigation", or needs to locate a past session by topic or ticket. Supports filtering by tag, project, summary, label, or branch. Use --deep to search inside artifact content. Falls back to filesystem scan if no manifest exists.
---

# Index

Find and catalog past sessions from the `~/.stoobz/sessions/` archive.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Process

### Manifest-First Path (default)

1. **Read `~/.stoobz/manifest.json`** — Parse the sessions array.

2. **Partition by status** — Separate entries into active (`status == "active"`) and archived (`status != "active"` or no `status` field). Active sessions display first.

3. **Apply filter** (if user provided an argument):
   - `/index` → show all sessions
   - `/index <term>` → case-insensitive search across: `tags`, `summary`, `label`, `project`, `branch`, `session_id` (partial UUID match), `chain_id`, `last_exchange` text
   - Multiple words are ANDed (all must match somewhere across fields)

### Active Sessions (shown first)

Display entries where `status == "active"` before archived sessions:

```markdown
## Active Sessions

| Project | Since | Last Active | Branch | Last Exchange | Resume |
|---------|-------|-------------|--------|---------------|--------|
| stoobz-web | 2h ago | 5m ago | main | "Nailed it! /persist the mig..." / "Persisted to ./stoobz/..." | `cd ~/... && claude --resume 2578...` |
```

- **Since:** Relative time from `started_at` ("2h ago", "1d ago")
- **Last Active:** Relative time from `last_activity`
- **Last Exchange:** User text / Assistant text (from `last_exchange`, already truncated at 80 chars)
- **Resume:** The `return_to` value, displayed as code
- If no active sessions, skip this section silently

### Archived Sessions

4. **Present the archived index:**

```markdown
## Session Index — ~/.stoobz/manifest.json (N archived sessions)

| Project | Date | Label | Summary | Artifacts | Tags |
|---------|------|-------|---------|-----------|------|
| my-project | 2026-02-13 | PROJ-1234 | Auth token refresh fix | T R P | elixir, auth |
| my-project | 2026-02-10 | auth-token-refresh | Token expiry investigation | T H P | elixir, phoenix |
| api-gateway | 2026-01-28 | rate-limiting | API rate limiting | T I | go, infrastructure |

**Legend:** T=TLDR C=Context R=Retro P=Hone H=Handoff I=Investigation
```

   **Artifact abbreviations:**
   - `T` = TLDR.md
   - `C` = CONTEXT_FOR_NEXT_SESSION.md
   - `R` = RETRO.md
   - `P` = HONE.md
   - `H` = HANDOFF.md
   - `I` = INVESTIGATION_SUMMARY.md or INVESTIGATION_CONTEXT.md

5. **For each result**, show the `source_dir` so the user can `cd` there and `/pickup`.

6. **If user is searching**, highlight matching results and show the summary field for context.

### `--active` Flag

Show only active sessions. Skip the archived section entirely.

### `--since <duration>` Flag

Filter all entries (active + archived) by recency.
- Duration formats: `1h`, `4h`, `1d`, `3d`, `1w`, `2w`
- Compare against `last_activity` (if present) or `date` field
- Show matching entries in their respective sections (active first, then archived)

### `--chain <term>` Flag

Group entries by `chain_id`, show the full work stream timeline:

```markdown
## Chain: brrp-migration (2 sessions, Feb 28 - Mar 1)

| # | Date | Project | Branch | Status | Summary / Last Exchange | Resume |
|---|------|---------|--------|--------|-------------------------|--------|
| 1 | Feb 28 | stoobz-api | main | archived | Schema migration deep dive... | cd ~/...api && claude ... |
| 2 | Mar 1 | stoobz-web | main | ACTIVE | "Nailed it! /persist the mig..." | cd ~/...web && claude ... |
```

- `/index --chain` (no term): show all chains, grouped by `chain_id`, sorted by most recent activity
- `/index --chain <term>`: filter chains by `chain_id`, `project`, or `summary` content matching the term
- Entries without a `chain_id` are shown separately under "Unchained Sessions"
- Within each chain, sort by `chain_position` ascending

### Deep Search — `--deep`

When invoked as `/index --deep <term>` (or `/index -d <term>`), search inside the actual archived artifact content:

1. **Grep `~/.stoobz/sessions/`** — Search all `.md` files under `~/.stoobz/sessions/` for the term (case-insensitive).

2. **Group by session** — Collect hits by their parent archive directory, not individual files.

3. **Present with context snippets:**

```markdown
## Deep Search — "auth-key" (2 hits across 1 session)

### my-app / 2026-02-12-usb-bundle
**TLDR.md:14** — ...the **api-key** rotation wasn't picking up the new value from env...
**INVESTIGATION_CONTEXT.md:87** — ...the **api-key** needs to be passed as a header, not a query param...

Source: ~/my-app
Tags: api, debugging, infrastructure
```

4. **Also run manifest search** — Show manifest matches first (fast), then deep matches below. This way the user sees both metadata hits and content hits.

5. **If no manifest exists**, deep search still works — it's just grep over `~/.stoobz/sessions/`.

### Filesystem Fallback (no manifest)

If `~/.stoobz/manifest.json` doesn't exist:

1. **Notify the user:** "No manifest found. Falling back to filesystem scan..."

2. **Scan `~/.stoobz/sessions/`** for directories containing session artifacts (`TLDR.md`, `RETRO.md`, `HONE.md`, `HANDOFF.md`, `INVESTIGATION_SUMMARY.md`, `INVESTIGATION_CONTEXT.md`).

3. **For each directory found:**
   - Read the first 5 lines of `TLDR.md` (if present) for the title and date
   - Note which artifacts exist
   - Note the most recent modification date

4. **Present the index** in the same table format as above (without tags, since those come from the manifest).

5. **Suggest:** "Run `/park --archive-system` to build a manifest from these artifacts for faster future lookups. Add `--all` to skip prompting, or `--dry-run` to preview first."

## Rules

- **Read only headers** — Don't load full file contents. The manifest has everything needed; for fallback, first 5 lines of TLDR.md is enough.
- **Sort by date** — Most recent first.
- **Fast** — This is a lookup tool. Don't analyze, just catalog.
- **Suggest pickup** — If a result has a `source_dir` with `CONTEXT_FOR_NEXT_SESSION.md`, note: "Has resume context — run `/pickup` from that directory."
- **Present to the user directly** — Don't write a file (this is a query, not an artifact).
- **Manifest is truth** — When manifest exists, trust it. Don't re-scan the filesystem.
