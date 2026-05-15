# Session Kit — Write-Artifact Protocol

The canonical contract every artifact-writing session-kit skill follows. Read this once; individual SKILL.md files reference it instead of restating it.

> **Why this exists.** See [ADR-0004](~/.stoobz/kb/adr/0004-session-kit-artifact-durability.md) — durable-first write-through with ledger replaces lazy-archive copy-at-`/park`.

---

## The Contract

When a session-kit skill produces an artifact, it MUST follow this ordering. The durable write is the canonical write; everything else is best-effort convenience.

```
1. archive write       → $SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/<rel-path>
2. verify              → file exists AND size > 0
3. ledger append       → append entry to <active-archive>/.session-artifacts.json
4. cwd mirror          → cwd/.stoobz/<rel-path>   (best-effort; warn on failure, don't raise)
```

If step 1 fails: the skill itself fails loudly. The artifact does not exist anywhere.
If step 2 fails: same — durable write didn't succeed; treat as step 1 failure.
If step 3 fails: same — the ledger is the system of record; no quiet drift.
If step 4 fails: log a warning to the operator, continue. The durable write succeeded.

## Path Semantics

**`<rel-path>` is the artifact's path relative to `.stoobz/`.** It preserves any nested structure.

| Skill produces                          | `<rel-path>`                              |
|------------------------------------------|-------------------------------------------|
| `cwd/.stoobz/TLDR.md`                    | `TLDR.md`                                 |
| `cwd/.stoobz/CONTEXT_FOR_NEXT_SESSION.md`| `CONTEXT_FOR_NEXT_SESSION.md`             |
| `cwd/.stoobz/rca/INVESTIGATION_SUMMARY.md` | `rca/INVESTIGATION_SUMMARY.md`          |
| `cwd/.stoobz/rca/evidence/screenshot.png`| `rca/evidence/screenshot.png`             |

**Both archive and mirror writes must `mkdir -p` the parent directory before writing.** Nested artifacts (RCA evidence, future multi-file skills) must not fail because the intermediate dir doesn't exist yet.

**The ledger entry is the full `<rel-path>`, not the leaf name.** Two skills writing files with the same basename in different subdirs do not collide.

## Active Archive Directory

Pre-allocated at session check-in (see [session-checkin.md](session-checkin.md)):

```
$SESSION_KIT_ROOT/sessions/<project>/<session-id>-active/
├── .session-artifacts.json     ← the ledger (created with empty artifacts: [])
└── <artifacts written here as the session progresses>
```

`<session-id>` is the Claude Code session UUID (from session-checkin's detection logic).
`<project>` is `basename $(git rev-parse --show-toplevel)` or `basename $(pwd)` (same as existing manifest logic).

At `/park` finalization, the dir is renamed:

```
<session-id>-active/  →  <date-label>/
```

## Ledger Schema (`.session-artifacts.json`)

**Schema version: 1.**

```json
{
  "schema_version": 1,
  "session_id": "<uuid>",
  "started_at": "<iso8601>",
  "source_dir": "/absolute/path/to/cwd",
  "artifacts": [
    {
      "name": "TLDR.md",
      "written_at": "2026-05-14T18:32:11Z",
      "skill": "tldr",
      "size_bytes": 1234
    },
    {
      "name": "rca/evidence/screenshot.png",
      "written_at": "2026-05-14T18:45:02Z",
      "skill": "rca",
      "size_bytes": 88720
    }
  ]
}
```

### Field rules

| Field             | Write semantics                                                                |
|-------------------|--------------------------------------------------------------------------------|
| `schema_version`  | Write-once at ledger init.                                                     |
| `session_id`      | Write-once at ledger init. Matches the session-checkin session_id.             |
| `started_at`      | Write-once at ledger init. Matches the manifest entry's `started_at`.          |
| `source_dir`      | Write-once at ledger init. Absolute path of cwd at session start.              |
| `artifacts`       | **Append-only.** Never reorder, never rewrite past entries.                    |

Inside an `artifacts[]` entry:
- `name` — the full `<rel-path>` (see Path Semantics above)
- `written_at` — ISO-8601 UTC of when the artifact was written to the archive
- `skill` — the SKILL.md frontmatter `name:` value of the skill that wrote it
- `size_bytes` — file size at write time, used by `/park` for verification

### Idempotency

The ledger is **append-only**, but artifacts themselves may be rewritten (e.g., `/tldr` invoked twice in one session, second invocation appends "Previous Session" history). In that case:

- The archive file is overwritten in place (durable write semantics unchanged).
- A new entry is appended to the ledger with the new `written_at` and `size_bytes`.
- Re-reading the ledger at `/park` time, the last entry per `name` wins.

This trades ledger size for simplicity (no in-place edits, no reordering). For typical sessions the ledger stays well under 10KB.

## Verification (used by `/park` and `/index --current-session`)

For each ledger entry:
1. The file at `<active-archive>/<name>` exists.
2. The file's current size matches the latest entry's `size_bytes`.

Mismatched size is a warning, not a fatal — operator may have edited the artifact manually between write and `/park`. `/park` surfaces the discrepancy and proceeds.

## Failure Policies

### Session-ID detection failure

Session-checkin first tries the cwd-encoded JSONL lookup, then falls back to git-root encoding (see session-checkin.md). **If both fail, no durable write is possible.**

In this degenerate state, the skill MUST fail loudly with a clear message:

```
Cannot establish session identity (no .jsonl in ~/.claude/projects/<encoded-cwd>
and no git root). Refusing to write artifact — durable-first cannot guarantee
the artifact's archive location. If you're running outside Claude Code, set
SESSION_KIT_SESSION_ID to a stable identifier and retry.
```

Rejected alternatives:
- *Synthetic ID*: creates a non-canonical session that doesn't reconcile with the manifest later.
- *Downgrade to cwd-only*: silently violates the ADR's durable-first principle — exactly the failure mode this redesign is supposed to eliminate.

### Active dir creation failure

If `mkdir -p` of the active archive dir fails at check-in, check-in fails loudly. Without the directory, no skill can write. This is a precondition, not a graceful-degradation case.

### Mirror failure

If the cwd mirror write fails (permissions, disk, etc.), log to the operator:

```
warn: cwd mirror failed for <rel-path>: <error>
      Durable write succeeded at <archive-path>.
      The artifact is preserved; only the working-dir copy is missing.
```

Skill continues normally. `/park` will not re-attempt the mirror — it's a one-shot best-effort.

### Verification mismatch at `/park`

If a ledger entry's file is missing or size doesn't match, `/park` surfaces the discrepancy but proceeds. Missing-file is logged; size-mismatch records the actual size in the manifest. Operator decides whether to investigate.

## What This Replaces

| Old (lazy archive)                                | New (durable-first)                                  |
|---------------------------------------------------|------------------------------------------------------|
| Skill writes to `cwd/.stoobz/<artifact>.md`       | Skill writes to archive first, then mirrors to cwd   |
| `/park` enumerates a hardcoded artifact allowlist | `/park` reads the ledger as authoritative            |
| `/park` failure mid-copy = data loss              | `/park` failure = orphan dir in archive, recoverable |
| Multi-session collision in `cwd/.stoobz/`         | Each session writes to its own `<session-id>-active/`|
| Brain-dump files in `.stoobz/` ambiguous to park  | Park only touches ledger-listed files                |

## References

- [ADR-0004](~/.stoobz/kb/adr/0004-session-kit-artifact-durability.md) — the *why*
- [session-checkin.md](session-checkin.md) — active dir pre-allocation, session ID detection
- [session-kit.md](session-kit.md) — overall kit architecture
