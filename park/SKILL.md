---
name: park
description: Park the current session by generating all session artifacts, archiving them to $SESSION_KIT_ROOT/sessions/<project>/<date-label>/ (default ~/.stoobz/), and updating the manifest. Use when the user says "/park", "park this session", "wrap up", "I'm done for now", "save everything", or wants to create a complete handoff package before leaving a session. Runs /tldr, /relay, and /prompt-lab in sequence, then archives. Supports --archive-system for retroactive cleanup of scattered .stoobz/ directories (with --select, --all, --dry-run, --clean flags).
---

# Park Session

Generate all session artifacts, archive them to `~/.stoobz/sessions/`, and clean up cwd. The "I'm stepping away, save everything" command.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Process

### Phase 1 — Generate Artifacts

1. **Announce** — Tell the user: "Parking this session. Generating artifacts..."

2. **Run each skill in sequence:**
   - `/tldr` → `TLDR.md` — Shareable session summary
   - `/relay` → `CONTEXT_FOR_NEXT_SESSION.md` — Resume context for next session
   - `/prompt-lab` → `PROMPT_LAB.md` — Original + optimized prompt

3. **For each skill, follow its full process** including:
   - Checking for existing files (merge, don't overwrite)
   - Using the correct output format from each skill's spec
   - Applying each skill's rules

### Phase 2 — Archive

4. **Determine project name:**
   - If in a git repo: `basename $(git rev-parse --show-toplevel)`
   - Otherwise: `basename $(pwd)`

5. **Determine label** (first match wins):
   - User provided an argument to `/park <label>` → use that label
   - Git branch name (if not `main`, `master`, `develop`) → use branch name
   - Slugify the first heading from TLDR.md → use that (max 50 chars, lowercase, hyphens)
   - Fallback → date only (no label suffix)

6. **Build archive path:**
   - Pattern: `~/.stoobz/sessions/<project>/<YYYY-MM-DD>-<label>/`
   - If path already exists, append `-2`, `-3`, etc.
   - `mkdir -p` the path

7. **Copy artifacts to archive:**

   | Copy to archive | Leave in cwd |
   |----------------|--------------|
   | `TLDR.md` | `CONTEXT_FOR_NEXT_SESSION.md` |
   | `PROMPT_LAB.md` | |
   | `RETRO.md` (if exists) | |
   | `HANDOFF.md` (if exists) | |
   | `INVESTIGATION_SUMMARY.md` (if exists) | |
   | `INVESTIGATION_CONTEXT.md` (if exists) | |
   | `evidence/` (if exists, `cp -r`) | |

8. **Clean up cwd** — Remove the copied artifacts from cwd (not `CONTEXT_FOR_NEXT_SESSION.md` — it stays as the relay baton for `/pickup`).

9. **Update manifest** — Read-modify-write `~/.stoobz/manifest.json`:
   - If file doesn't exist, create it with `{"sessions": []}`
   - If file is corrupted/unparseable, back it up as `manifest.json.bak` and create fresh
   - Check if an entry with the same `archive_path` already exists → update in place
   - Otherwise append a new entry

   **Manifest entry schema:**
   ```json
   {
     "id": "<YYYY-MM-DD>-<label>",
     "project": "<project-name>",
     "date": "<YYYY-MM-DD>",
     "label": "<label>",
     "summary": "<first heading text from TLDR.md>",
     "source_dir": "<absolute path to cwd>",
     "archive_path": "sessions/<project>/<YYYY-MM-DD>-<label>",
     "branch": "<git branch or null>",
     "artifacts": ["TLDR.md", "PROMPT_LAB.md"],
     "tags": ["elixir", "auth"],
     "type": "session"
   }
   ```

   **Tags** — Auto-detect 2-5 tags from TLDR.md content:
   - Languages: elixir, python, javascript, typescript, ruby, go, rust, sql, bash, powershell
   - Frameworks: phoenix, ecto, oban, react, next, absinthe, liveview
   - Topics: debugging, performance, migration, refactor, investigation, auth, deployment, testing, infrastructure

10. **Print summary:**

```
Session parked and archived.

  Archive:  ~/.stoobz/sessions/<project>/<date-label>/
  Artifacts archived: TLDR.md, PROMPT_LAB.md
  Relay:    CONTEXT_FOR_NEXT_SESSION.md (stays in cwd)
  Tags:     elixir, phoenix, auth

  Run /pickup in this directory to resume.
  Run /index to find past sessions.
```

## `--archive-system` — Retroactive Cleanup

When invoked as `/park --archive-system`, skip artifact generation and instead archive existing scattered `.stoobz/` directories as complete units.

### Flags

| Flag | Behavior |
|------|----------|
| `--select` | Interactive picker — present table, user picks which to archive **(DEFAULT)** |
| `--all` | Archive everything found, no prompting |
| `--dry-run` | Show what would happen, take no action |
| `--clean` | Auto-remove originals after verified archive (default: ask per-source) |

Flags combine: `--all --clean` archives and cleans everything. `--dry-run --all` shows full plan.

### Step 1 — Scan

Run `find ~ -maxdepth 4 -type d -name ".stoobz"` to find all `.stoobz/` directories.

**Skip:** any `.stoobz/` that is under `~/.stoobz/` (already archived). Skip empty dirs.

Also scan for **loose artifacts** — `TLDR.md`, `RETRO.md`, `HANDOFF.md`, `PROMPT_LAB.md`, `CONTEXT_FOR_NEXT_SESSION.md`, `INVESTIGATION_SUMMARY.md`, `INVESTIGATION_CONTEXT.md` — sitting in project roots (not inside any `.stoobz/`), not under `~/.stoobz/`.

### Step 2 — Build session units

Classify each discovered `.stoobz/` directory:

| Pattern | Structure | Result |
|---------|-----------|--------|
| **A — Flat files** | `.stoobz/` contains only files (no subdirs) | One session unit — `cp -r` everything |
| **B — Subdirectories** | `.stoobz/` contains only subdirs | Each subdir is a separate session unit |
| **C — Mixed** | `.stoobz/` has both files and subdirs | Each subdir → separate unit; loose files → one additional unit |

**Loose artifacts** found in project roots are grouped by project into one additional unit per project.

For each session unit, resolve:

- **Project** — nearest git repo basename (via `git -C <path> rev-parse --show-toplevel`), or parent directory basename
- **Label** — subdir name if from Pattern B/C, else slugified first heading from TLDR.md (max 50 chars, lowercase, hyphens), else parent directory name
- **Date** — most recent mtime among files in the unit
- **Summary** — first heading from TLDR.md if present, else first heading from any `.md` file in the unit, else "No summary"
- **Files** — full list of filenames in the unit

### Step 3 — Present findings

Show all discovered units in a table:

```markdown
## Found Session Units

| # | Source | Files | Date | Summary |
|---|--------|-------|------|---------|
| 1 | ~/my-app/.stoobz/ (7 files) | PLAN.md, deployment-methods.md, +5 | 2026-02-12 | USB bundle |
| 2 | ~/dotfiles/.stoobz/ci-pipeline/ (3 files) | TLDR.md, PROMPT_LAB.md, +1 | 2026-02-12 | Git cleanup |
| 3 | ~/dotfiles/.stoobz/configs/ (5 files) | direnv, gh, +3 | 2026-02-12 | No summary |
| 4 | ~/work/api/ (2 loose files) | TLDR.md, RETRO.md | 2026-02-08 | API rate limiting |
```

- `--select` (default): Show table, then ask "Enter numbers to archive (e.g. 1,3,4), or `all`:"
- `--all`: Show table, then proceed without prompting
- `--dry-run`: Show table with the header "## Dry Run — No changes will be made", then stop

### Step 4 — Archive each selected unit

For each selected unit:

1. **Build archive path:** `~/.stoobz/sessions/<project>/<YYYY-MM-DD>-<label>/`
   - If path exists, append `-2`, `-3`, etc.
   - `mkdir -p` the path

2. **Copy entire subtree:** `cp -r <source>/* <archive-path>/`
   - For Pattern A: copy all files from `.stoobz/`
   - For Pattern B/C subdirs: copy all files from the subdir
   - For Pattern C loose files: copy the loose files
   - For loose artifacts: copy the individual files
   - `CONTEXT_FOR_NEXT_SESSION.md` is included in the archive (these are old sessions nobody is picking up)

3. **Verify copy:** compare file count in source vs archive. Only proceed to cleanup if counts match.

4. **Update manifest** — same schema as normal `/park` (Step 9 above), with `"type": "session"` and `artifacts` array listing **all files** in the unit.

### Step 5 — Clean up originals

- **Default:** ask per-source: "Remove originals from `<path>`? [y/N]"
- **`--clean`:** auto-remove without asking
- **Partially-selected `.stoobz/` dirs (Pattern B/C):** only remove the archived subdirs or files, not the entire `.stoobz/` directory
- **Never remove** until copy verification passes (Step 4.3)

### Step 6 — Print summary

```
Archive system complete.

  Archived: 4 session units
  Manifest: ~/.stoobz/manifest.json (4 entries added)
  Cleaned:  3 source locations removed

  Run /index to browse all sessions.
```

## Rules

- **All or nothing** (Phase 1) — Generate all three core artifacts. For individual artifacts, use the specific skill.
- **Always archive** — Phase 2 runs automatically after Phase 1. No flag needed.
- **Respect existing files** — Each skill handles its own file existence check.
- **Don't re-explain** — Just execute. The user wants results, not descriptions.
- **No questions** — Generate all three without asking. Use best judgment for content.
- **CONTEXT_FOR_NEXT_SESSION.md never moves** (normal mode) — It stays in cwd as the relay baton for `/pickup`. In `--archive-system` mode, it gets archived too (old sessions nobody is picking up).
- **Manifest is append-only** — Never remove entries, only add or update in place.
- **Idempotent** — Re-parking the same session updates the existing archive entry rather than creating duplicates.
