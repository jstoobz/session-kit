"""Unit tests for `sk index`.

Manifest is the source of truth for active + archived. Filesystem scan covers
`--orphans` only; `--deep` greps inside archived artifact text. Tests build
small fixture manifests + on-disk sessions trees and exercise filter / since /
chain / active / orphans / deep / json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from session_kit import index as idx
from session_kit.__main__ import app
from session_kit.common import EXIT_OK, EXIT_USAGE

runner = CliRunner()


# --- Fixtures -------------------------------------------------------------


def _write_manifest(sk_root: Path, sessions: list[dict]) -> Path:
    p = sk_root / "manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"sessions": sessions}, indent=2), encoding="utf-8")
    return p


def _make_archived(
    *,
    sid: str,
    project: str,
    label: str,
    summary: str,
    tags: list[str] | None = None,
    branch: str | None = None,
    date: str = "2026-05-15",
    artifacts: list[str] | None = None,
    chain_id: str | None = None,
    chain_position: int | None = None,
    parent_chain_id: str | None = None,
    checkpoint_nodes: list[int] | None = None,
    last_activity: str | None = None,
) -> dict:
    return {
        "id": f"{date}-{label}",
        "session_id": sid,
        "project": project,
        "date": date,
        "label": label,
        "summary": summary,
        "branch": branch,
        "tags": tags or [],
        "artifacts": artifacts or ["TLDR.md"],
        "status": "archived",
        "chain_id": chain_id,
        "chain_position": chain_position,
        "parent_chain_id": parent_chain_id,
        "checkpoint_nodes": checkpoint_nodes,
        "last_activity": last_activity or f"{date}T12:00:00Z",
        "started_at": last_activity or f"{date}T11:00:00Z",
        "archive_path": f"sessions/{project}/{date}-{label}",
    }


def _make_active(
    *,
    sid: str,
    project: str,
    started_at: str = "2026-05-17T08:00:00Z",
    last_activity: str = "2026-05-17T09:00:00Z",
    tags: list[str] | None = None,
    branch: str | None = "main",
    last_user_text: str | None = "hello",
) -> dict:
    return {
        "session_id": sid,
        "project": project,
        "branch": branch,
        "tags": tags or [],
        "status": "active",
        "started_at": started_at,
        "last_activity": last_activity,
        "return_to": f"cd ~/{project} && claude --resume {sid}",
        "last_exchange": {
            "user": {"text": last_user_text, "timestamp": last_activity} if last_user_text else None,
            "assistant": None,
        },
    }


def _make_active_dir(sk_root: Path, project: str, sid: str, ledger_artifact_count: int = 0) -> Path:
    d = sk_root / "sessions" / project / f"{sid}-active"
    d.mkdir(parents=True, exist_ok=True)
    ledger = d / ".session-artifacts.json"
    ledger.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "session_id": sid,
                "artifacts": [
                    {"name": f"art{i}.md", "skill": "x"} for i in range(ledger_artifact_count)
                ],
            }
        )
    )
    return d


def _make_archived_artifact(sk_root: Path, project: str, archive_id: str, filename: str, body: str) -> Path:
    d = sk_root / "sessions" / project / archive_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(body, encoding="utf-8")
    return p


# --- Empty manifest -------------------------------------------------------


def test_empty_manifest_renders_empty(sk_root, fake_home, project_cwd):
    _write_manifest(sk_root, [])
    result = runner.invoke(app, ["index"])
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    assert "(no sessions found)" in result.stdout


def test_no_manifest_file_renders_empty(sk_root, fake_home, project_cwd):
    result = runner.invoke(app, ["index"])
    assert result.exit_code == EXIT_OK
    assert "(no sessions found)" in result.stdout


# --- Default: archived listing --------------------------------------------


def test_default_lists_archived_sessions(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="a", project="alpha", label="auth-fix", summary="Token bug",
                           tags=["auth"], date="2026-04-01"),
            _make_archived(sid="b", project="beta", label="rate-limit", summary="API ratelimit",
                           tags=["go"], date="2026-04-10"),
        ],
    )
    result = runner.invoke(app, ["index"])
    assert result.exit_code == EXIT_OK
    assert "auth-fix" in result.stdout
    assert "rate-limit" in result.stdout
    # Sorted newest first
    rl = result.stdout.index("rate-limit")
    af = result.stdout.index("auth-fix")
    assert rl < af


# --- Filter ---------------------------------------------------------------


@pytest.mark.parametrize(
    "field,build,term,expect",
    [
        ("tags", lambda: _make_archived(sid="x", project="p", label="L", summary="S", tags=["foo"]), "foo", "L"),
        ("summary", lambda: _make_archived(sid="x", project="p", label="L", summary="needle here"), "needle", "L"),
        ("label", lambda: _make_archived(sid="x", project="p", label="my-bug", summary="S"), "my-bug", "my-bug"),
        ("project", lambda: _make_archived(sid="x", project="elixir-thing", label="L", summary="S"), "elixir", "L"),
        ("branch", lambda: _make_archived(sid="x", project="p", label="L", summary="S", branch="feat/x"), "feat/x", "L"),
    ],
)
def test_filter_matches_each_field(sk_root, fake_home, project_cwd, field, build, term, expect):
    _write_manifest(sk_root, [build()])
    result = runner.invoke(app, ["index", term])
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    assert expect in result.stdout, f"expected {expect!r} when filtering field {field!r} by {term!r}: {result.stdout}"


def test_filter_case_insensitive(sk_root, fake_home, project_cwd):
    _write_manifest(sk_root, [_make_archived(sid="x", project="p", label="L", summary="S", tags=["FooBar"])])
    result = runner.invoke(app, ["index", "foobar"])
    assert result.exit_code == EXIT_OK
    assert "| L |" in result.stdout or " L " in result.stdout


def test_filter_excludes_non_match(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="x", project="p", label="keep", summary="S", tags=["a"]),
            _make_archived(sid="y", project="p", label="drop", summary="S", tags=["b"]),
        ],
    )
    result = runner.invoke(app, ["index", "a"])
    assert result.exit_code == EXIT_OK
    assert "keep" in result.stdout
    assert "drop" not in result.stdout


# --- --active --------------------------------------------------------------


def test_active_only_shows_active_entries(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="a", project="p", label="L", summary="S"),
            _make_active(sid="liveA", project="p", tags=["foo"]),
        ],
    )
    result = runner.invoke(app, ["index", "--active"])
    assert result.exit_code == EXIT_OK
    assert "Active Sessions" in result.stdout
    assert "liveA" in result.stdout
    assert "Session Index" not in result.stdout  # archived section suppressed
    assert "L" in result.stdout  # 'L' is the label, but archived section is hidden


def test_active_filter_combination(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_active(sid="alive1", project="alpha", tags=["foo"]),
            _make_active(sid="alive2", project="beta", tags=["bar"]),
        ],
    )
    result = runner.invoke(app, ["index", "--active", "foo"])
    assert result.exit_code == EXIT_OK
    assert "alive1" in result.stdout
    assert "alive2" not in result.stdout


# --- --orphans -------------------------------------------------------------


def test_orphans_surfaces_unregistered_active_dir(sk_root, fake_home, project_cwd):
    # Registered: in manifest
    _write_manifest(sk_root, [_make_active(sid="registered", project="p")])
    # Make active dir for the registered one (should NOT appear as orphan)
    _make_active_dir(sk_root, "p", "registered", ledger_artifact_count=3)
    # Make active dir for unregistered (orphan)
    _make_active_dir(sk_root, "p", "orphan-sid", ledger_artifact_count=2)
    result = runner.invoke(app, ["index", "--orphans"])
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    assert "Orphans" in result.stdout
    assert "orphan-sid"[:8] in result.stdout
    assert "registered"[:8] not in result.stdout


def test_orphans_skips_registered_active_dir(sk_root, fake_home, project_cwd):
    _write_manifest(sk_root, [_make_active(sid="registered-sid", project="p")])
    _make_active_dir(sk_root, "p", "registered-sid")
    result = runner.invoke(app, ["index", "--orphans"])
    assert result.exit_code == EXIT_OK
    assert "(no orphaned active dirs found)" in result.stdout


def test_orphans_empty_when_no_active_dirs(sk_root, fake_home, project_cwd):
    _write_manifest(sk_root, [_make_archived(sid="x", project="p", label="L", summary="S")])
    result = runner.invoke(app, ["index", "--orphans"])
    assert result.exit_code == EXIT_OK
    assert "(no orphaned active dirs found)" in result.stdout


# --- --chain ---------------------------------------------------------------


def test_chain_groups_by_chain_id(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="a", project="p", label="L1", summary="s1",
                           chain_id="my-chain", chain_position=1, date="2026-04-01"),
            _make_archived(sid="b", project="p", label="L2", summary="s2",
                           chain_id="my-chain", chain_position=2, date="2026-04-02"),
            _make_archived(sid="c", project="p", label="Lx", summary="sx", date="2026-04-03"),
        ],
    )
    result = runner.invoke(app, ["index", "--chain"])
    assert result.exit_code == EXIT_OK
    assert "my-chain" in result.stdout
    assert "Unchained Sessions" in result.stdout
    assert "Lx" in result.stdout


def test_chain_shows_fork_annotation(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="parent1", project="p", label="P1", summary="s",
                           chain_id="parent-chain", chain_position=1, date="2026-04-01"),
            _make_archived(sid="fork1", project="p", label="F1", summary="s",
                           chain_id="forked", chain_position=1,
                           parent_chain_id="parent-chain", checkpoint_nodes=[1],
                           date="2026-04-05"),
        ],
    )
    result = runner.invoke(app, ["index", "--chain"])
    assert result.exit_code == EXIT_OK
    assert "forked" in result.stdout
    assert "forked from parent-chain" in result.stdout
    assert "nodes 1" in result.stdout


# --- --since ---------------------------------------------------------------


def test_since_absolute_date_filter(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="old", project="p", label="old", summary="s", date="2026-01-01"),
            _make_archived(sid="new", project="p", label="new", summary="s", date="2026-04-01"),
        ],
    )
    result = runner.invoke(app, ["index", "--since", "2026-03-01"])
    assert result.exit_code == EXIT_OK
    assert "new" in result.stdout
    assert "| old |" not in result.stdout  # the label column would be "old"


def test_since_relative_week(sk_root, fake_home, project_cwd):
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(days=2)
    stale = now - timedelta(days=30)
    _write_manifest(
        sk_root,
        [
            _make_archived(
                sid="stale", project="p", label="stale", summary="s",
                date=stale.strftime("%Y-%m-%d"),
                last_activity=stale.strftime("%Y-%m-%dT12:00:00Z"),
            ),
            _make_archived(
                sid="fresh", project="p", label="fresh", summary="s",
                date=fresh.strftime("%Y-%m-%d"),
                last_activity=fresh.strftime("%Y-%m-%dT12:00:00Z"),
            ),
        ],
    )
    result = runner.invoke(app, ["index", "--since", "week"])
    assert result.exit_code == EXIT_OK
    assert "fresh" in result.stdout
    assert "stale" not in result.stdout


def test_since_invalid_value_returns_usage_error(sk_root, fake_home, project_cwd):
    _write_manifest(sk_root, [])
    result = runner.invoke(app, ["index", "--since", "yesterday"])
    assert result.exit_code == EXIT_USAGE


# --- --deep ---------------------------------------------------------------


def test_deep_finds_artifact_content(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [_make_archived(sid="x", project="p", label="L", summary="S", date="2026-04-01")],
    )
    _make_archived_artifact(
        sk_root, "p", "2026-04-01-L", "TLDR.md",
        "line one\nthis line has WIDGET-9001 in it\nline three\n",
    )
    result = runner.invoke(app, ["index", "--deep", "widget-9001"])
    assert result.exit_code == EXIT_OK
    assert "Deep Search" in result.stdout
    assert "TLDR.md:2" in result.stdout
    assert "WIDGET-9001" in result.stdout


# --- --json ---------------------------------------------------------------


def test_json_default_schema(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [
            _make_archived(sid="a", project="p", label="L", summary="S",
                           tags=["foo"], date="2026-04-01"),
            _make_active(sid="alive", project="p", tags=["bar"]),
        ],
    )
    result = runner.invoke(app, ["index", "--json"])
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "active" in payload
    assert "archived" in payload
    assert "orphans" in payload
    assert "deep" in payload
    assert "chain_view" in payload
    assert len(payload["active"]) == 1
    assert len(payload["archived"]) == 1
    assert payload["chain_view"] is False
    assert payload["deep"] is None


def test_json_includes_deep_when_flag_set(sk_root, fake_home, project_cwd):
    _write_manifest(
        sk_root,
        [_make_archived(sid="x", project="p", label="L", summary="S", date="2026-04-01")],
    )
    _make_archived_artifact(sk_root, "p", "2026-04-01-L", "TLDR.md", "needle line\n")
    result = runner.invoke(app, ["index", "--deep", "needle", "--json"])
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["deep"]["pattern"] == "needle"
    assert len(payload["deep"]["hits"]) == 1
    assert payload["deep"]["hits"][0]["artifact"] == "TLDR.md"


def test_json_orphans_schema(sk_root, fake_home, project_cwd):
    _write_manifest(sk_root, [])
    _make_active_dir(sk_root, "myproj", "orphan-id", ledger_artifact_count=4)
    result = runner.invoke(app, ["index", "--orphans", "--json"])
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert len(payload["orphans"]) == 1
    o = payload["orphans"][0]
    assert o["project"] == "myproj"
    assert o["session_id"] == "orphan-id"
    assert o["ledger_artifact_count"] == 4
    assert "active_dir" in o
    assert "last_mtime" in o
