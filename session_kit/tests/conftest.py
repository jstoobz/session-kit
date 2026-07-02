"""Pytest fixtures for session_kit.

Each test that touches the manifest, ledger, or JSONL resolution gets:
  - a tmp SESSION_KIT_ROOT
  - an isolated fake $HOME (so resolution looks at fake ~/.claude/projects)
  - cwd set to a tmp project dir

`mock_jsonl_session` writes a small but representative JSONL session file
under fake $HOME and returns its session_id so tests can resolve to it.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from session_kit.common import encode_path


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # pathlib.Path.home() consults HOME on POSIX; ensure os.path.expanduser also follows.
    return home


@pytest.fixture()
def sk_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "stoobz"
    monkeypatch.setenv("SESSION_KIT_ROOT", str(root))
    return root


@pytest.fixture()
def project_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cwd = tmp_path / "proj"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


@pytest.fixture()
def mock_jsonl_session(fake_home: Path, project_cwd: Path):
    """Factory: write a JSONL session file under fake $HOME for the given cwd.

    Returns (session_id, jsonl_path). Each call creates a fresh session_id.
    """
    def _make(cwd: Path | None = None, records: list[dict] | None = None) -> tuple[str, Path]:
        target_cwd = cwd or project_cwd
        proj_dir = fake_home / ".claude" / "projects" / encode_path(target_cwd)
        proj_dir.mkdir(parents=True, exist_ok=True)
        sid = str(uuid.uuid4()).lower()
        path = proj_dir / f"{sid}.jsonl"
        recs = records if records is not None else [
            {"type": "user", "timestamp": "2026-05-17T10:00:00Z",
             "message": {"content": "first message"}},
            {"type": "assistant", "timestamp": "2026-05-17T10:00:05Z",
             "message": {"content": [{"type": "text", "text": "first reply"}]}},
        ]
        with path.open("w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        return sid, path

    return _make
