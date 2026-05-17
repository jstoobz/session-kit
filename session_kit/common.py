"""Shared helpers for session_kit subcommands.

Three groups of utilities live here:
  - Exit-code constants (the CLI protocol)
  - Path / config resolution (SESSION_KIT_ROOT, project name, JSONL location)
  - Session-id resolution + atomic JSON RMW under file lock

Everything that touches the manifest or ledger goes through atomic_update_json.
Everything that resolves a session-id goes through resolve_session_id.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from filelock import FileLock, Timeout

# --- Exit-code protocol -----------------------------------------------------

EXIT_OK = 0
EXIT_DURABILITY_FAIL = 1
EXIT_WARN = 2
EXIT_USAGE = 3

# --- Time helpers -----------------------------------------------------------


def now_iso() -> str:
    """ISO-8601 UTC with second precision and explicit Z suffix.

    Matches the format the protocol pinned in the four hardening commits —
    no microseconds, no naive datetimes.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --- Path / config resolution ----------------------------------------------


def session_kit_root() -> Path:
    return Path(os.environ.get("SESSION_KIT_ROOT") or (Path.home() / ".stoobz"))


def encode_path(path: Path) -> str:
    """Mirror Claude Code's project-dir encoding: replace `/` with `-`."""
    return str(path).replace("/", "-")


def projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def git_toplevel(cwd: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    line = out.stdout.strip()
    return Path(line) if line else None


def git_branch(cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    line = out.stdout.strip()
    return line or None


def project_name(cwd: Path) -> str:
    root = git_toplevel(cwd)
    return (root or cwd).name


def return_to(cwd: Path, session_id: str) -> str:
    home = str(Path.home())
    cwd_str = str(cwd)
    if cwd_str == home or cwd_str.startswith(home + "/"):
        cwd_str = "~" + cwd_str[len(home):]
    return f"cd {cwd_str} && claude --resume {session_id}"


# --- Session-id resolution --------------------------------------------------


@dataclass
class SessionResolution:
    session_id: str
    resolved_via: str  # "jsonl" | "git-root" | "cached" | "synthesized"
    session_file: Path | None  # the JSONL file (tier 1/2 only)
    cwd: Path


def _latest_jsonl(encoded_dir: Path) -> Path | None:
    if not encoded_dir.is_dir():
        return None
    files = sorted(
        (p for p in encoded_dir.glob("*.jsonl") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def resolve_session_id(cwd: Path) -> SessionResolution:
    """Three-tier resolution chain. Never fails — falls through to synthesis."""
    proj_dir = projects_dir()

    # Tier 1: cwd-encoded JSONL
    cand = _latest_jsonl(proj_dir / encode_path(cwd))
    if cand is not None:
        sid = cand.stem
        return SessionResolution(sid, "jsonl", cand, cwd)

    # Tier 2: git-root-encoded JSONL
    root = git_toplevel(cwd)
    if root is not None and root != cwd:
        cand = _latest_jsonl(proj_dir / encode_path(root))
        if cand is not None:
            sid = cand.stem
            return SessionResolution(sid, "git-root", cand, cwd)

    # Tier 3: cached UUID in cwd/.stoobz/.session-id, else synthesize
    stoobz_dir = cwd / ".stoobz"
    stoobz_dir.mkdir(parents=True, exist_ok=True)
    cache = stoobz_dir / ".session-id"
    if cache.is_file():
        sid = cache.read_text(encoding="utf-8").strip()
        if sid:
            return SessionResolution(sid, "cached", None, cwd)

    sid = str(uuid.uuid4()).lower()
    cache.write_text(sid + "\n", encoding="utf-8")
    return SessionResolution(sid, "synthesized", None, cwd)


# --- Atomic JSON read-modify-write under lock ------------------------------


def atomic_update_json(
    path: Path,
    mutate: Callable[[Any], Any],
    *,
    default: Any | None = None,
    timeout: float = 10.0,
) -> Any:
    """Read `path`, apply `mutate(data) -> data'`, atomic-rename back.

    Held under an exclusive file lock for the duration of the RMW. The lock
    file sits beside `path` (`<path>.lock`). Default is used when the file
    does not yet exist; if it does exist but is empty / unparseable, we treat
    that as default too (a fresh write replaces it).

    Returns the post-mutate data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock", timeout=timeout)
    with lock:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            try:
                data = json.loads(text) if text.strip() else default
            except json.JSONDecodeError:
                # Back up the corrupt file before clobbering it.
                backup = path.with_suffix(path.suffix + ".bak")
                backup.write_text(text, encoding="utf-8")
                data = default
        else:
            data = default
        data = mutate(data)
        _atomic_write_json(path, data)
    return data


def _atomic_write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


# --- JSONL streaming for last-exchange extraction --------------------------


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Stream a JSONL file one record at a time. Bad lines are skipped."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# --- Error helpers ----------------------------------------------------------


@contextmanager
def emit_durability_abort(label: str) -> Iterator[None]:
    """Wrap a hard-gate operation; convert exceptions to a clear abort message."""
    try:
        yield
    except Timeout as exc:
        print(f"abort: lock timeout during {label}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_DURABILITY_FAIL)
    except OSError as exc:
        print(f"abort: {label} failed: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_DURABILITY_FAIL)
