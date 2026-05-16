---
name: tldr
description: Generate a concise TLDR.md summary of the current session's key findings, decisions, and outcomes. Use when the user says "/tldr", "write a tldr", "summarize this session", "create a summary", or wants a shareable document capturing what happened in this conversation. Produces a clean, engineer-friendly markdown file ready to share before diving into full analysis.
---

# TLDR

Generate a `TLDR.md` file summarizing the current session for sharing with other engineers.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Check-In (precondition)

Before the Process section runs, invoke `/checkin` in **silent mode** as a precondition. Export `INVOKING_SKILL=tldr` first so `/checkin` appends `"tldr"` to the session's `skills_used` on this skill's behalf. See [checkin/SKILL.md](../checkin/SKILL.md) for the protocol details.

If `/checkin` aborts (mkdir or ledger creation failure — the only durability conditions that fail loudly), this skill aborts too. Do not proceed to the Process section. Do not write any artifact.

The canonical pattern: inline `/checkin`'s Reference Implementation at the top of this skill's single bash invocation (see [Reference Implementation](#reference-implementation) below). That keeps `SESSION_ID`, `ACTIVE_DIR`, `LEDGER`, etc. in scope for the artifact write.

## Process

This skill writes its artifact under the **durable-first protocol**. See [write-artifact-protocol.md](../write-artifact-protocol.md) for the full contract.

The prose steps below describe the ceremony for orientation; the executable form is [Reference Implementation](#reference-implementation) — a single bash invocation that bundles `/checkin`'s scaffolding work with `tldr`'s artifact write, so shell state persists across the whole skill.

1. **Conversation review** (Claude analysis, not shell) — extract:
   - **What was investigated/built** — the problem or task
   - **Key findings** — discoveries, root causes, data points
   - **Decisions made** — choices and their rationale
   - **Actions taken** — code changes, config updates, commands run
   - **Open items** — unresolved questions, next steps, follow-ups

2. **Compose the TLDR content** in the [Output Format](#output-format) below. If `$ACTIVE_DIR/TLDR.md` already exists, preserve its current top-level section under a new `## Previous Session` heading and put the new content above; this is a rolling history with latest first. (The check happens inside the bundled bash block, against the archive — not cwd.)

3. **Single bash invocation** that does, in order:
   - Run `/checkin`'s Reference Implementation with `INVOKING_SKILL=tldr` to resolve `SESSION_ID`, ensure scaffolding, and export `ACTIVE_DIR`, `LEDGER`, `NOW`.
   - **Durable write:** write the composed content to `$ACTIVE_DIR/TLDR.md`. Verify the file exists and `size > 0`. Abort on failure.
   - **Append ledger entry:** append to `$LEDGER`'s `artifacts` array:
     ```json
     { "name": "TLDR.md", "written_at": "$NOW", "skill": "tldr", "size_bytes": <bytes> }
     ```
     Abort on failure (inconsistent state).
   - **Mirror to cwd (best-effort):** `mkdir -p ./.stoobz && cp "$ACTIVE_DIR/TLDR.md" ./.stoobz/TLDR.md`. On failure, log a warning (format from [write-artifact-protocol.md § Mirror failure](../write-artifact-protocol.md)) but do not abort — the durable write is canonical.
   - Print confirmation: archive path, cwd path (or mirror warning).

## Output Format

```markdown
# TLDR: {One-line title}

**Date:** {YYYY-MM-DD}
**Session:** {branch or context identifier}
**Author:** Claude + {user}

---

## Context

{1-2 sentences: what prompted this work and why it matters}

## Key Findings

- {Finding 1 — be specific, include numbers/names}
- {Finding 2}
- {Finding 3}

## Decisions

| Decision           | Rationale |
| ------------------ | --------- |
| {What was decided} | {Why}     |

## Changes Made

- {File or system changed}: {what changed}

## Open Items

- [ ] {Next step or unresolved question}
- [ ] {Follow-up needed}

---

_Generated from Claude Code session — see full conversation for details._
```

## Rules

- **Brevity over completeness** — if it takes more than 2 minutes to read, it's too long
- **Specifics over generalities** — include actual file names, numbers, error messages, not vague descriptions
- **Skip sections with no content** — if no decisions were made, omit the Decisions table
- **No jargon expansion** — engineers reading this know the stack; don't explain what Oban or Ecto are
- **One file, flat structure** — no subdirectories, no companion files
- The canonical write location is `$ACTIVE_DIR/TLDR.md`; cwd `.stoobz/TLDR.md` is a best-effort mirror, not the source of truth
- The ledger entry's `name` is `TLDR.md` (no leading path; the artifact lives at the archive root)
- All shell work runs in a single `Bash` invocation. See [checkin/SKILL.md § Execution Discipline](../checkin/SKILL.md#execution-discipline) and the [Reference Implementation](#reference-implementation) below.

## Reference Implementation

Run as a single `Bash` tool invocation. The leading section is the canonical `/checkin` block from [checkin/SKILL.md § Reference Implementation](../checkin/SKILL.md#reference-implementation), copied inline so its exported variables (`ACTIVE_DIR`, `LEDGER`, `NOW`, `SESSION_ID`) remain in scope for the artifact write. Pre-compose `TLDR_BODY` in Claude before running.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Caller pre-sets: TLDR_BODY="$(cat <<'EOF' ... EOF)"
: "${TLDR_BODY:?TLDR_BODY must be set with the composed TLDR markdown}"

# Identify this skill so /checkin records it in skills_used (silent mode).
export INVOKING_SKILL="tldr"
export MODE="silent"

# --- BEGIN inlined /checkin Reference Implementation ---
# (paste the full block from checkin/SKILL.md § Reference Implementation here;
#  it resolves SESSION_ID, ensures scaffolding, updates the manifest, and
#  exports SESSION_ID SESSION_FILE RESOLVED_VIA ACTIVE_DIR LEDGER MANIFEST PROJECT NOW.)
# --- END inlined /checkin Reference Implementation ---

ARCHIVE_TLDR="$ACTIVE_DIR/TLDR.md"

# --- Rolling history: prepend existing archive content if present ---
if [ -s "$ARCHIVE_TLDR" ]; then
  PREV="$(cat "$ARCHIVE_TLDR")"
  printf '%s\n\n## Previous Session\n\n%s\n' "$TLDR_BODY" "$PREV" > "$ARCHIVE_TLDR"
else
  printf '%s\n' "$TLDR_BODY" > "$ARCHIVE_TLDR"
fi

# --- Verify durable write ---
if [ ! -s "$ARCHIVE_TLDR" ]; then
  echo "abort: durable write verification failed at $ARCHIVE_TLDR (missing or empty)" >&2
  exit 1
fi
SIZE_BYTES="$(wc -c < "$ARCHIVE_TLDR" | tr -d ' ')"

# --- Append ledger entry ---
TMP_LEDGER="$(mktemp)"
if ! jq \
      --arg name "TLDR.md" \
      --arg now "$NOW" \
      --arg skill "tldr" \
      --argjson size "$SIZE_BYTES" \
      '.artifacts += [{name: $name, written_at: $now, skill: $skill, size_bytes: $size}]' \
      "$LEDGER" > "$TMP_LEDGER"; then
  rm -f "$TMP_LEDGER"
  echo "abort: ledger append failed at $LEDGER" >&2
  exit 1
fi
mv "$TMP_LEDGER" "$LEDGER"

# --- Mirror to cwd (best-effort) ---
MIRROR_STATUS="ok"
if ! ( mkdir -p ./.stoobz && cp "$ARCHIVE_TLDR" ./.stoobz/TLDR.md ) 2>/tmp/sk-mirror.err; then
  MIRROR_STATUS="failed"
  printf 'warn: cwd mirror failed for TLDR.md: %s\n      Durable write succeeded at %s.\n      The artifact is preserved; only the working-dir copy is missing.\n' \
    "$(cat /tmp/sk-mirror.err)" "$ARCHIVE_TLDR" >&2
fi

# --- Confirmation ---
echo "TLDR written:"
echo "  archive: $ARCHIVE_TLDR ($SIZE_BYTES bytes)"
if [ "$MIRROR_STATUS" = "ok" ]; then
  echo "  cwd:     ./.stoobz/TLDR.md"
else
  echo "  cwd:     (mirror failed — see warning above)"
fi
```

**Why inline the `/checkin` block.** The exported variables (`ACTIVE_DIR`, `LEDGER`, `NOW`) are what the artifact write needs. Spawning `/checkin` as a separate process and re-resolving here would work, but the inline form is one fewer place for the resolution chain to disagree with itself.

**`TLDR_BODY` composition.** Claude composes the TLDR content (using [Output Format](#output-format)) before running this block, then injects it via a heredoc-bound `TLDR_BODY` variable. Pre-composing in Claude keeps the bash purely mechanical — no nested heredoc-within-heredoc complexity, no shell-quote escaping of markdown content.
