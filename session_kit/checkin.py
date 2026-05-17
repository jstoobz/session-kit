"""sk checkin — durable-first session registration + scaffolding + liveness refresh.

The Python port of the bash Reference Implementation in `checkin/SKILL.md`. Every
fix the four hardening commits encoded must survive here:

  - ISO-8601 UTC timestamps with second precision, explicit Z (no microseconds,
    no naive datetimes — see common.now_iso)
  - JSONL extraction scoped to the resolved SESSION_FILE only; never globs
    `~/.claude/projects/<encoded>/*.jsonl`
  - last_exchange real-user filter: type==user, not isMeta, not isSidechain,
    content is string OR array with first elem type==text (excludes tool_result)
  - Scaffolding-only idempotency: active dir and ledger are create-if-missing
    only; ledger write-once metadata never rewritten
  - Liveness fields (last_activity, last_exchange when extractable) refresh on
    every invocation, including re-entry
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
    SessionResolution,
    atomic_update_json,
    atomic_write_text,
    git_branch,
    iter_jsonl,
    now_iso,
    project_name,
    resolve_session_id,
    return_to,
    session_kit_root,
    today_iso,
)


def _extract_started_at(session_file: Path | None, fallback: str) -> str:
    """First record's `timestamp` field, else fallback."""
    if session_file is None or not session_file.is_file():
        return fallback
    try:
        with session_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = rec.get("timestamp")
                if ts:
                    return ts
                return fallback
    except OSError:
        return fallback
    return fallback


def _is_real_user(rec: dict) -> bool:
    if rec.get("type") != "user":
        return False
    if rec.get("isMeta") is True:
        return False
    if rec.get("isSidechain") is True:
        return False
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            return True
    return False


def _user_text(rec: dict) -> str:
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return first.get("text", "") or ""
    return ""


def _assistant_text(rec: dict) -> str:
    content = rec.get("message", {}).get("content")
    if isinstance(content, list) and content:
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "") or ""
    return ""


def _truncate(s: str, n: int = 80) -> str:
    if len(s) > n:
        return s[:n] + "..."
    return s


def _extract_last_exchange(session_file: Path | None) -> dict | None:
    """Scan the session JSONL forward; keep the LAST real-user + LAST assistant."""
    if session_file is None or not session_file.is_file():
        return None

    last_user: dict | None = None
    last_assistant: dict | None = None

    for rec in iter_jsonl(session_file):
        if _is_real_user(rec):
            last_user = rec
        elif rec.get("type") == "assistant":
            text = _assistant_text(rec)
            if text:
                last_assistant = rec

    if last_user is None and last_assistant is None:
        return None

    def _entry_user(rec: dict | None) -> dict | None:
        if rec is None:
            return None
        return {
            "text": _truncate(_user_text(rec)),
            "timestamp": rec.get("timestamp"),
        }

    def _entry_assistant(rec: dict | None) -> dict | None:
        if rec is None:
            return None
        return {
            "text": _truncate(_assistant_text(rec)),
            "timestamp": rec.get("timestamp"),
        }

    return {
        "user": _entry_user(last_user),
        "assistant": _entry_assistant(last_assistant),
    }


def _initial_ledger(session_id: str, started_at: str, cwd: Path) -> dict:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "started_at": started_at,
        "source_dir": str(cwd),
        "artifacts": [],
    }


def _new_manifest_entry(
    *,
    session_id: str,
    project: str,
    cwd: Path,
    now: str,
    started_at: str,
    last_exchange: dict | None,
    return_to_cmd: str | None,
    branch: str | None,
    append_skill: str,
) -> dict:
    return {
        "id": session_id,
        "project": project,
        "date": today_iso(),
        "label": None,
        "summary": None,
        "source_dir": str(cwd),
        "archive_path": None,
        "branch": branch,
        "artifacts": [],
        "tags": [],
        "type": "session",
        "status": "active",
        "session_id": session_id,
        "return_to": return_to_cmd,
        "chain_id": None,
        "chain_position": None,
        "previous_session_id": None,
        "parent_chain_id": None,
        "checkpoint_nodes": None,
        "started_at": started_at,
        "last_activity": now,
        "last_exchange": last_exchange,
        "skills_used": [append_skill] if append_skill else [],
    }


def _append_dedupe(seq: list[str] | None, item: str) -> list[str]:
    seq = list(seq or [])
    if item and item not in seq:
        seq.append(item)
    return seq


def run_checkin(
    *,
    cwd: Path,
    mode: str,  # "explicit" | "silent"
    invoking: str | None,
    json_out: bool,
    debug: bool,
) -> dict:
    """Run the full ceremony; return a result dict (also the --json payload)."""
    if mode not in ("explicit", "silent"):
        raise ValueError(f"mode must be 'explicit' or 'silent', got {mode!r}")

    sk_root = session_kit_root()
    now = now_iso()
    res: SessionResolution = resolve_session_id(cwd)
    proj = project_name(cwd)
    branch = git_branch(cwd)

    active_dir = sk_root / "sessions" / proj / f"{res.session_id}-active"
    ledger_path = active_dir / ".session-artifacts.json"
    manifest_path = sk_root / "manifest.json"

    if debug:
        print(
            f"[debug] session_id={res.session_id} via={res.resolved_via} "
            f"project={proj} active_dir={active_dir}",
            file=sys.stderr,
        )

    # --- Hard gate: scaffolding ---
    try:
        sk_root.mkdir(parents=True, exist_ok=True)
        active_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"abort: mkdir failed at {active_dir}: {exc}", file=sys.stderr)
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    # started_at: prefer first JSONL entry; fall back to NOW (tier-3)
    started_at = _extract_started_at(res.session_file, fallback=now)

    # Ledger: create if missing; NEVER modify if present (write-once scaffolding)
    if not ledger_path.exists():
        try:
            atomic_write_text(
                ledger_path,
                json.dumps(
                    _initial_ledger(res.session_id, started_at, cwd),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )
        except OSError as exc:
            print(
                f"abort: ledger creation failed at {ledger_path}: {exc}",
                file=sys.stderr,
            )
            raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    last_exchange = _extract_last_exchange(res.session_file)

    # Determine append_skill per mode rules
    if mode == "explicit":
        append_skill = "checkin"
    elif invoking:
        append_skill = invoking
    else:
        append_skill = ""

    return_to_cmd: str | None
    if res.resolved_via in ("jsonl", "git-root"):
        return_to_cmd = return_to(cwd, res.session_id)
    else:
        return_to_cmd = None

    # --- Atomic manifest RMW ---
    is_first_holder = {"value": False}

    def mutate(data: Any) -> Any:
        data = data or {"sessions": []}
        sessions = data.get("sessions") or []
        idx = next(
            (i for i, s in enumerate(sessions) if s.get("session_id") == res.session_id),
            None,
        )
        if idx is None:
            is_first_holder["value"] = True
            sessions.append(
                _new_manifest_entry(
                    session_id=res.session_id,
                    project=proj,
                    cwd=cwd,
                    now=now,
                    started_at=started_at,
                    last_exchange=last_exchange,
                    return_to_cmd=return_to_cmd,
                    branch=branch,
                    append_skill=append_skill,
                )
            )
        else:
            entry = sessions[idx]
            # Liveness refresh — never touch write-once metadata.
            entry["last_activity"] = now
            if last_exchange is not None:
                entry["last_exchange"] = last_exchange
            if append_skill:
                entry["skills_used"] = _append_dedupe(
                    entry.get("skills_used"), append_skill
                )
            sessions[idx] = entry
        data["sessions"] = sessions
        return data

    try:
        atomic_update_json(manifest_path, mutate, default={"sessions": []})
    except OSError as exc:
        print(
            f"abort: manifest update failed at {manifest_path}: {exc}",
            file=sys.stderr,
        )
        raise typer.Exit(code=EXIT_DURABILITY_FAIL)

    is_first = is_first_holder["value"]

    result = {
        "session_id": res.session_id,
        "active_dir": str(active_dir),
        "ledger": str(ledger_path),
        "manifest": str(manifest_path),
        "resolved_via": res.resolved_via,
        "is_first": is_first,
        "mode": mode,
        "appended_skill": append_skill or None,
    }

    if json_out:
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return result

    if mode == "explicit":
        if is_first:
            print(
                f"Session checked in: {res.session_id} → {active_dir}; "
                f"ledger initialized (resolved via {res.resolved_via})"
            )
        else:
            print(f"Already checked in: {res.session_id}")
    # silent mode: no stdout

    return result


def command(
    explicit: bool = typer.Option(
        False, "--explicit", help="User-invoked /checkin; appends 'checkin' to skills_used."
    ),
    silent: bool = typer.Option(
        False, "--silent", help="Precondition mode invoked by another skill; no stdout."
    ),
    invoking: str = typer.Option(
        None,
        "--invoking",
        metavar="SKILL",
        help="Name of the skill invoking /checkin as a silent precondition; appended to skills_used.",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit a machine-readable JSON result on stdout."
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Print resolution + path debug info to stderr."
    ),
) -> None:
    """Register the current Claude Code session and pre-allocate the durable archive.

    Mode resolution:
      --explicit          → emit messages; append 'checkin' to skills_used
      --silent            → no stdout; if --invoking <skill>, append it instead
      (neither)           → defaults to silent

    Exit codes:
      0  success (new check-in or re-entry)
      1  durability failure (mkdir or ledger / manifest write) — caller MUST abort
      3  usage error (bad args)
    """
    if explicit and silent:
        print("usage: --explicit and --silent are mutually exclusive", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)

    mode = "explicit" if explicit else "silent"

    run_checkin(
        cwd=Path.cwd().resolve(),
        mode=mode,
        invoking=invoking,
        json_out=json_out,
        debug=debug,
    )
    raise typer.Exit(code=EXIT_OK)
