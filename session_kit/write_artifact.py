"""sk write-artifact — durable-first artifact write.

Implements the four-step contract from `write-artifact-protocol.md`:

  1. archive write   → $ACTIVE_DIR/<rel-path>
  2. verify          → file exists AND size > 0
  3. ledger append   → entry in $ACTIVE_DIR/.session-artifacts.json
  4. cwd mirror      → cwd/.stoobz/<rel-path> (best-effort)

Calls checkin in silent mode internally as a precondition so callers (skill
markdown) only need this one binary invocation per artifact.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import typer

from .checkin import run_checkin
from .common import (
    EXIT_DURABILITY_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    EXIT_WARN,
    atomic_update_json,
    atomic_write_text,
    now_iso,
)


def _read_content(content_file: Path | None, content_stdin: bool) -> str:
    if content_file is not None:
        return content_file.read_text(encoding="utf-8")
    if content_stdin:
        if sys.stdin.isatty():
            print(
                "usage: --content-stdin set but stdin is a TTY (no piped input)",
                file=sys.stderr,
            )
            raise typer.Exit(code=EXIT_USAGE)
        return sys.stdin.read()
    print(
        "usage: must supply --content-file <path> or --content-stdin",
        file=sys.stderr,
    )
    raise typer.Exit(code=EXIT_USAGE)


def _validate_rel_path(rel_path: str) -> Path:
    p = Path(rel_path)
    if p.is_absolute():
        print(f"usage: --artifact must be a relative path, got {rel_path!r}", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)
    parts = p.parts
    if any(part == ".." for part in parts):
        print(f"usage: --artifact must not contain '..' segments: {rel_path!r}", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)
    if not parts:
        print("usage: --artifact must be non-empty", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)
    return p


def run_write_artifact(
    *,
    cwd: Path,
    skill: str,
    rel_path: str,
    content: str,
    mirror: bool,
    json_out: bool,
) -> dict:
    rel = _validate_rel_path(rel_path)

    # Precondition: checkin in silent mode, recording the invoking skill.
    checkin_result = run_checkin(
        cwd=cwd,
        mode="silent",
        invoking=skill,
        json_out=False,
        debug=False,
    )

    active_dir = Path(checkin_result["active_dir"])
    ledger_path = Path(checkin_result["ledger"])

    archive_target = active_dir / rel
    now = now_iso()

    # --- Step 1: archive write ---
    try:
        atomic_write_text(archive_target, content)
    except OSError as exc:
        print(
            f"abort: archive write failed at {archive_target}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    # --- Step 2: verify ---
    try:
        size = archive_target.stat().st_size
    except OSError as exc:
        print(
            f"abort: durable write verification failed at {archive_target}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)
    if size == 0:
        print(
            f"abort: durable write verification failed at {archive_target} (empty)",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    # --- Step 3: ledger append ---
    entry = {
        "name": str(rel).replace(os.sep, "/"),
        "written_at": now,
        "skill": skill,
        "size_bytes": size,
    }

    def mutate(data: Any) -> Any:
        data = data or {}
        data.setdefault("artifacts", [])
        data["artifacts"].append(entry)
        return data

    try:
        atomic_update_json(ledger_path, mutate, default={"artifacts": []})
    except OSError as exc:
        print(
            f"abort: ledger append failed at {ledger_path}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    # --- Step 4: cwd mirror (best-effort) ---
    mirror_status = "skipped"
    mirror_path = cwd / ".stoobz" / rel
    mirror_error: str | None = None
    if mirror:
        try:
            mirror_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive_target, mirror_path)
            mirror_status = "ok"
        except OSError as exc:
            mirror_status = "failed"
            mirror_error = str(exc)
            print(
                f"warn: cwd mirror failed for {entry['name']}: {exc}\n"
                f"      Durable write succeeded at {archive_target}.\n"
                f"      The artifact is preserved; only the working-dir copy is missing.",
                file=sys.stderr,
            )

    result = {
        "session_id": checkin_result["session_id"],
        "skill": skill,
        "artifact": entry["name"],
        "archive_path": str(archive_target),
        "mirror_path": str(mirror_path) if mirror else None,
        "mirror_status": mirror_status,
        "mirror_error": mirror_error,
        "size_bytes": size,
        "written_at": now,
        "ledger": str(ledger_path),
    }

    if json_out:
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        print(f"{skill} wrote {entry['name']}:")
        print(f"  archive: {archive_target} ({size} bytes)")
        if mirror:
            if mirror_status == "ok":
                print(f"  cwd:     {mirror_path}")
            else:
                print("  cwd:     (mirror failed — see warning above)")

    return result


def command(
    skill: str = typer.Option(
        ..., "--skill", metavar="NAME", help="SKILL.md frontmatter name of the writer."
    ),
    artifact: str = typer.Option(
        ...,
        "--artifact",
        metavar="REL-PATH",
        help="Artifact path relative to the active archive (and cwd/.stoobz/ mirror).",
    ),
    content_file: Path = typer.Option(
        None,
        "--content-file",
        metavar="PATH",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Read artifact content from this file.",
    ),
    content_stdin: bool = typer.Option(
        False, "--content-stdin", help="Read artifact content from stdin."
    ),
    no_mirror: bool = typer.Option(
        False, "--no-mirror", help="Skip the cwd best-effort mirror step."
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit a machine-readable JSON result on stdout."
    ),
) -> None:
    """Write a session artifact under the durable-first protocol.

    Calls `sk checkin --silent --invoking <skill>` internally as a precondition,
    then writes the archive, verifies, appends a ledger entry, and (best-effort)
    mirrors to cwd/.stoobz/.

    Exit codes:
      0  full success (durable + mirror, if requested)
      1  durability failure — caller MUST abort and surface
      2  mirror-only failure (reserved; durable succeeded; warning emitted)
      3  usage error (bad args)
    """
    if content_file is not None and content_stdin:
        print(
            "usage: --content-file and --content-stdin are mutually exclusive",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_USAGE)
    content = _read_content(content_file, content_stdin)

    result = run_write_artifact(
        cwd=Path.cwd().resolve(),
        skill=skill,
        rel_path=artifact,
        content=content,
        mirror=not no_mirror,
        json_out=json_out,
    )

    # Mirror failures are warnings, not durability failures.
    if result["mirror_status"] == "failed":
        raise typer.Exit(code=EXIT_WARN)
    raise typer.Exit(code=EXIT_OK)
