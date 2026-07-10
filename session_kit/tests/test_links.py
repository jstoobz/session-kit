"""Link guard: offline lychee over the repo's own files.

Dead in-repo links were a founding complaint; the second-order failure is
the checker itself rotting (a config key that stops parsing after a tool
upgrade disables the guard silently behind a green-looking target). So this
test asserts a zero exit for ANY failure class — dead link or config parse
error alike. It skips only when lychee isn't installed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("lychee") is None, reason="lychee not installed")
def test_repo_links_resolve_offline():
    result = subprocess.run(
        ["lychee", "--offline", "--no-progress", "--config", "lychee.toml", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"lychee exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
    )
