"""sk park-finalize — finalize a session: rename active dir, flip manifest, append chain block.

The mechanical close-out half of /park. The orchestrator (park/SKILL.md) composes
TLDR / RELAY / HONE bodies and writes them via `sk write-artifact`, then hands
label / summary / tags to this subcommand. We:

  1. Resolve session-id (three-tier).
  2. Read the ledger as authoritative artifact list (last-write-wins dedupe).
  3. Verify each ledger entry exists in the active dir; surface missing as warning.
  4. Rename $ACTIVE_DIR → $SESSION_KIT_ROOT/sessions/<project>/<date>-<label>/
     (with -2, -3, ... collision suffix).
  5. Atomic manifest RMW: status active→archived; populate id/label/summary/
     archive_path/artifacts/tags; chain naming for first-node sessions.
  6. Append chain metadata block to cwd/.stoobz/CONTEXT_FOR_NEXT_SESSION.md
     unless --no-chain-block.

Already-archived session_id is a friendly no-op (exit 0, message to stderr) —
the operator's intent (session parked) is already met. Don't clobber the archive.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from .common import (
    EXIT_DURABILITY_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    EXIT_WARN,
    atomic_update_json,
    now_iso,
    project_name,
    resolve_session_id,
    session_kit_root,
    today_iso,
)


def _read_ledger_artifacts(ledger_path: Path) -> list[dict]:
    if not ledger_path.is_file():
        return []
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return list(data.get("artifacts") or [])


def _dedupe_last_write_wins(entries: list[dict]) -> list[str]:
    """Return artifact names in first-occurrence order; later writes update in place."""
    order: list[str] = []
    seen: set[str] = set()
    for e in entries:
        name = e.get("name")
        if not name:
            continue
        if name not in seen:
            seen.add(name)
            order.append(name)
    return order


def _find_archive_path(parent: Path, base: str) -> Path:
    target = parent / base
    if not target.exists():
        return target
    n = 2
    while True:
        target = parent / f"{base}-{n}"
        if not target.exists():
            return target
        n += 1


def _existing_manifest_entry(manifest_path: Path, session_id: str) -> dict | None:
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    for s in data.get("sessions") or []:
        if s.get("session_id") == session_id:
            return s
    return None


def _append_chain_block(
    baton_path: Path,
    *,
    chain_id: str | None,
    session_id: str,
    chain_position: int,
) -> tuple[str, str | None]:
    """Append chain metadata block to the relay baton.

    Returns (status, error). status in {"appended", "already-present", "missing", "failed"}.
    """
    if not baton_path.is_file():
        return "missing", f"baton not found at {baton_path}"
    try:
        body = baton_path.read_text(encoding="utf-8")
    except OSError as exc:
        return "failed", str(exc)

    # Idempotency: if a block tagged with this session_id already exists, skip.
    if "session-kit-chain" in body and f"session_id: {session_id}" in body:
        return "already-present", None

    block = (
        "<!-- session-kit-chain\n"
        f"chain_id: {chain_id if chain_id is not None else 'null'}\n"
        f"session_id: {session_id}\n"
        f"chain_position: {chain_position}\n"
        "-->\n"
    )
    if body and not body.endswith("\n"):
        body += "\n"
    body += "\n" + block
    try:
        baton_path.write_text(body, encoding="utf-8")
    except OSError as exc:
        return "failed", str(exc)
    return "appended", None


def run_park_finalize(
    *,
    cwd: Path,
    label: str,
    summary: str,
    tags: list[str] | None,
    chain_id_override: str | None,
    no_chain_block: bool,
    json_out: bool,
    debug: bool,
) -> dict:
    sk_root = session_kit_root()
    now = now_iso()
    date = today_iso()
    res = resolve_session_id(cwd)
    proj = project_name(cwd)

    project_sessions_dir = sk_root / "sessions" / proj
    active_dir = project_sessions_dir / f"{res.session_id}-active"
    ledger_path = active_dir / ".session-artifacts.json"
    manifest_path = sk_root / "manifest.json"

    if debug:
        print(
            f"[debug] session_id={res.session_id} project={proj} "
            f"active_dir={active_dir}",
            file=sys.stderr,
        )

    # --- Idempotent re-park: already archived → friendly no-op ---
    existing = _existing_manifest_entry(manifest_path, res.session_id)
    if existing is not None and existing.get("status") == "archived":
        prior_path = existing.get("archive_path") or "(unknown)"
        msg = (
            f"already archived: session {res.session_id[:8]}... is at "
            f"{prior_path}; nothing to do."
        )
        result = {
            "session_id": res.session_id,
            "status": "already-archived",
            "archive_path": str(sk_root / prior_path) if prior_path != "(unknown)" else None,
            "label": existing.get("label"),
            "summary": existing.get("summary"),
            "artifacts": existing.get("artifacts") or [],
            "tags": existing.get("tags") or [],
            "chain_id": existing.get("chain_id"),
            "chain_position": existing.get("chain_position"),
            "missing_artifacts": [],
            "chain_block_status": "skipped",
            "chain_block_error": None,
            "manifest": str(manifest_path),
        }
        if json_out:
            json.dump(result, sys.stdout)
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            print(msg, file=sys.stderr)
        return result

    if not active_dir.is_dir():
        print(
            f"abort: active directory not found at {active_dir}; nothing to finalize.",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    # --- Read + verify the ledger ---
    ledger_entries = _read_ledger_artifacts(ledger_path)
    artifact_names = _dedupe_last_write_wins(ledger_entries)
    missing: list[str] = [n for n in artifact_names if not (active_dir / n).is_file()]
    for name in missing:
        print(
            f"warn: ledger lists artifact {name!r} but no file at {active_dir / name}",
            file=sys.stderr,
        )

    # --- Compute archive path with collision suffix ---
    base = f"{date}-{label}"
    try:
        project_sessions_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"abort: project sessions dir creation failed at {project_sessions_dir}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    archive_path = _find_archive_path(project_sessions_dir, base)
    archive_id = archive_path.name

    # --- Rename active → archive ---
    try:
        active_dir.rename(archive_path)
    except OSError as exc:
        print(
            f"abort: archive rename failed {active_dir} → {archive_path}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    # --- Atomic manifest RMW ---
    relative_archive = f"sessions/{proj}/{archive_id}"

    def mutate(data: Any) -> Any:
        data = data or {"sessions": []}
        sessions = data.get("sessions") or []
        idx = next(
            (i for i, s in enumerate(sessions) if s.get("session_id") == res.session_id),
            None,
        )
        if idx is None:
            entry = {
                "id": archive_id,
                "project": proj,
                "date": date,
                "label": label,
                "summary": summary,
                "source_dir": str(cwd),
                "archive_path": relative_archive,
                "branch": None,
                "artifacts": list(artifact_names),
                "tags": list(tags or []),
                "type": "session",
                "status": "archived",
                "session_id": res.session_id,
                "return_to": None,
                "chain_id": chain_id_override or label,
                "chain_position": 1,
                "previous_session_id": None,
                "parent_chain_id": None,
                "checkpoint_nodes": None,
                "started_at": now,
                "last_activity": now,
                "last_exchange": None,
                "skills_used": ["park"],
            }
            sessions.append(entry)
        else:
            entry = dict(sessions[idx])
            entry["status"] = "archived"
            entry["id"] = archive_id
            entry["label"] = label
            entry["summary"] = summary
            entry["date"] = date
            entry["archive_path"] = relative_archive
            entry["artifacts"] = list(artifact_names)
            entry["last_activity"] = now
            if tags is not None:
                entry["tags"] = list(tags)

            current_chain_position = entry.get("chain_position")
            current_chain_id = entry.get("chain_id")
            if chain_id_override:
                entry["chain_id"] = chain_id_override
            elif current_chain_position in (None, 1) and (
                current_chain_id is None or current_chain_id == res.session_id
            ):
                entry["chain_id"] = label
            # else: keep inherited chain_id from /pickup

            if entry.get("chain_position") is None:
                entry["chain_position"] = 1
            sessions[idx] = entry
        data["sessions"] = sessions
        return data

    try:
        post_data = atomic_update_json(
            manifest_path, mutate, default={"sessions": []}
        )
    except OSError as exc:
        print(
            f"abort: manifest update failed at {manifest_path}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    updated_entry: dict = {}
    for s in post_data.get("sessions", []):
        if s.get("session_id") == res.session_id:
            updated_entry = s
            break

    # --- Chain metadata block ---
    chain_status = "skipped"
    chain_error: str | None = None
    baton_path = cwd / ".stoobz" / "CONTEXT_FOR_NEXT_SESSION.md"
    if not no_chain_block:
        chain_status, chain_error = _append_chain_block(
            baton_path,
            chain_id=updated_entry.get("chain_id"),
            session_id=res.session_id,
            chain_position=updated_entry.get("chain_position") or 1,
        )
        if chain_status == "failed":
            print(
                f"warn: chain metadata append failed at {baton_path}: {chain_error}",
                file=sys.stderr,
            )
        elif chain_status == "missing":
            print(
                f"warn: relay baton not found at {baton_path}; chain block not appended",
                file=sys.stderr,
            )

    result = {
        "session_id": res.session_id,
        "status": "archived",
        "archive_path": str(archive_path),
        "archive_id": archive_id,
        "label": label,
        "summary": summary,
        "tags": updated_entry.get("tags") or [],
        "artifacts": list(artifact_names),
        "missing_artifacts": missing,
        "chain_id": updated_entry.get("chain_id"),
        "chain_position": updated_entry.get("chain_position"),
        "chain_block_status": chain_status,
        "chain_block_error": chain_error,
        "manifest": str(manifest_path),
    }

    if json_out:
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        artifacts_display = ", ".join(artifact_names) if artifact_names else "(none)"
        tags_display = ", ".join(result["tags"]) if result["tags"] else "(none)"
        chain_pos = result["chain_position"] or 1
        print("Session parked and archived.")
        print()
        print(f"  Archive:   {archive_path}/")
        print(f"  Artifacts: {artifacts_display}")
        print(f"  Relay:     {baton_path} (stays for /pickup)")
        print(f"  Tags:      {tags_display}")
        print(f"  Session:   {res.session_id[:8]}... (archived)")
        if result["chain_id"]:
            print(
                f"  Chain:     {result['chain_id']} "
                f"(node {chain_pos} of {chain_pos})"
            )
        print()
        print("  /pickup  — resume from this directory (continues chain)")
        print("  /index   — find past sessions")

    return result


def command(
    label: str = typer.Option(
        ...,
        "--label",
        metavar="SLUG",
        help="Date-label suffix for the archive dir (e.g., 'scripts-as-tools-substrate').",
    ),
    summary: str = typer.Option(
        ...,
        "--summary",
        metavar="TEXT",
        help="One-line session summary (typically derived from TLDR heading).",
    ),
    tags: str = typer.Option(
        None,
        "--tags",
        metavar="CSV",
        help="Comma-separated tags. Replaces existing manifest tags. Omit to keep existing.",
    ),
    chain_id: str = typer.Option(
        None,
        "--chain-id",
        metavar="ID",
        help="Override the chain_id (rare; operator-supplied).",
    ),
    no_chain_block: bool = typer.Option(
        False,
        "--no-chain-block",
        help="Skip appending chain metadata to the relay baton.",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit a machine-readable JSON result on stdout."
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Print resolution + path debug info to stderr."
    ),
) -> None:
    """Finalize a parked session: rename active dir, flip manifest, append chain block.

    Exit codes:
      0  success (or already-archived no-op)
      1  durability failure (rename, mkdir, manifest update)
      2  warning (missing ledger artifacts surfaced, chain block append failed)
      3  usage error
    """
    if not label.strip():
        print("usage: --label must be a non-empty slug", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)
    if not summary.strip():
        print("usage: --summary must be a non-empty string", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)

    tag_list: list[str] | None
    if tags is None:
        tag_list = None
    else:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    result = run_park_finalize(
        cwd=Path.cwd().resolve(),
        label=label.strip(),
        summary=summary.strip(),
        tags=tag_list,
        chain_id_override=chain_id,
        no_chain_block=no_chain_block,
        json_out=json_out,
        debug=debug,
    )

    if result.get("status") == "already-archived":
        raise typer.Exit(code=EXIT_OK)

    if result.get("missing_artifacts") or result.get("chain_block_status") == "failed":
        raise typer.Exit(code=EXIT_WARN)
    raise typer.Exit(code=EXIT_OK)
