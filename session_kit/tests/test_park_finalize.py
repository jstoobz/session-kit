"""Unit tests for sk park-finalize.

Setup pattern: drive a session through write_artifact a few times to populate
the active dir + ledger + manifest, then call run_park_finalize and inspect
the resulting archive + manifest state.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from session_kit import park_finalize as pf_mod
from session_kit import write_artifact as wa_mod
from session_kit.__main__ import app
from session_kit.common import EXIT_DURABILITY_FAIL, EXIT_OK, EXIT_USAGE, EXIT_WARN

runner = CliRunner()


# --- Helpers --------------------------------------------------------------


def _write_tldr_relay_hone(cwd: Path) -> None:
    """Populate active dir + ledger with three canonical artifacts."""
    for skill, name, body in (
        ("park", "TLDR.md", "# tldr body\n"),
        ("park", "CONTEXT_FOR_NEXT_SESSION.md", "# relay body\n"),
        ("park", "HONE.md", "# hone body\n"),
    ):
        wa_mod.run_write_artifact(
            cwd=cwd,
            skill=skill,
            rel_path=name,
            content=body,
            mirror=True,
            json_out=False,
        )


def _load_manifest(sk_root: Path) -> dict:
    return json.loads((sk_root / "manifest.json").read_text())


def _entry_for(sk_root: Path, session_id: str) -> dict:
    for s in _load_manifest(sk_root)["sessions"]:
        if s.get("session_id") == session_id:
            return s
    raise AssertionError(f"no manifest entry for {session_id}")


# --- Basic finalize -------------------------------------------------------


def test_basic_finalize_renames_active_and_flips_manifest(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)

    result = pf_mod.run_park_finalize(
        cwd=project_cwd,
        label="my-feature",
        summary="What we did",
        tags=["python", "refactor"],
        chain_id_override=None,
        no_chain_block=False,
        json_out=False,
        debug=False,
    )

    proj = project_cwd.name
    expected_dir = sk_root / "sessions" / proj / "2026-05-17-my-feature"
    # Date in test runs uses today_iso(); cannot pin without monkeypatch — use the actual archive_path.
    archive_path = Path(result["archive_path"])
    assert archive_path.is_dir()
    assert archive_path.parent == sk_root / "sessions" / proj
    assert archive_path.name.endswith("-my-feature")

    # Old active dir is gone
    assert not (sk_root / "sessions" / proj / f"{sid}-active").exists()

    entry = _entry_for(sk_root, sid)
    assert entry["status"] == "archived"
    assert entry["id"] == archive_path.name
    assert entry["label"] == "my-feature"
    assert entry["summary"] == "What we did"
    assert entry["archive_path"] == f"sessions/{proj}/{archive_path.name}"
    assert set(entry["artifacts"]) == {"TLDR.md", "CONTEXT_FOR_NEXT_SESSION.md", "HONE.md"}
    assert entry["tags"] == ["python", "refactor"]
    # Chain naming: first-node session → chain_id = label
    assert entry["chain_id"] == "my-feature"
    assert entry["chain_position"] == 1


def test_artifacts_dedupe_last_write_wins(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    mock_jsonl_session()
    for body in ("v1\n", "v2\n", "v3\n"):
        wa_mod.run_write_artifact(
            cwd=project_cwd, skill="park", rel_path="TLDR.md",
            content=body, mirror=False, json_out=False,
        )
    sid = _load_manifest(sk_root)["sessions"][0]["session_id"]
    pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["artifacts"] == ["TLDR.md"]


# --- Collision handling ---------------------------------------------------


def test_collision_appends_numeric_suffix(
    sk_root, fake_home, project_cwd, mock_jsonl_session, monkeypatch
):
    monkeypatch.setattr(pf_mod, "today_iso", lambda: "2026-05-17")
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)

    proj = project_cwd.name
    # Pre-create both 2026-05-17-feature and 2026-05-17-feature-2
    (sk_root / "sessions" / proj / "2026-05-17-feature").mkdir(parents=True)
    (sk_root / "sessions" / proj / "2026-05-17-feature-2").mkdir(parents=True)

    result = pf_mod.run_park_finalize(
        cwd=project_cwd, label="feature", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    assert Path(result["archive_path"]).name == "2026-05-17-feature-3"


# --- Missing artifacts → warning -----------------------------------------


def test_missing_ledger_artifact_surfaces_warning(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    # Hand-delete a file the ledger references
    proj = project_cwd.name
    active_dir = sk_root / "sessions" / proj / f"{sid}-active"
    (active_dir / "HONE.md").unlink()

    result = pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    assert "HONE.md" in result["missing_artifacts"]
    # Archive still happened
    assert Path(result["archive_path"]).is_dir()
    # Manifest still flipped
    entry = _entry_for(sk_root, sid)
    assert entry["status"] == "archived"


def test_cli_missing_artifact_exits_warn(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    proj = project_cwd.name
    (sk_root / "sessions" / proj / f"{sid}-active" / "HONE.md").unlink()

    result = runner.invoke(
        app,
        ["park-finalize", "--label", "x", "--summary", "x", "--no-chain-block"],
    )
    assert result.exit_code == EXIT_WARN, result.stdout + result.stderr


# --- Chain naming ---------------------------------------------------------


def test_chain_naming_first_node_sets_chain_id_to_label(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    pf_mod.run_park_finalize(
        cwd=project_cwd, label="my-label", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["chain_id"] == "my-label"
    assert entry["chain_position"] == 1


def test_chain_naming_preserves_inherited_chain_id(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    # Simulate /pickup having inherited chain metadata
    manifest_path = sk_root / "manifest.json"
    m = json.loads(manifest_path.read_text())
    m["sessions"][0]["chain_id"] = "original-chain"
    m["sessions"][0]["chain_position"] = 3
    m["sessions"][0]["previous_session_id"] = "abc-prev"
    manifest_path.write_text(json.dumps(m, indent=2, sort_keys=True))

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="new-park-label", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["chain_id"] == "original-chain"
    assert entry["chain_position"] == 3
    assert entry["previous_session_id"] == "abc-prev"


def test_chain_id_override_wins(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    pf_mod.run_park_finalize(
        cwd=project_cwd, label="lbl", summary="x",
        tags=None, chain_id_override="forced-chain",
        no_chain_block=True, json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["chain_id"] == "forced-chain"


# --- Chain metadata block on relay baton ----------------------------------


def test_chain_block_appended_to_relay_baton(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    baton = project_cwd / ".stoobz" / "CONTEXT_FOR_NEXT_SESSION.md"
    assert baton.is_file(), "mirror should have written baton"

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="block-test", summary="x",
        tags=None, chain_id_override=None, no_chain_block=False,
        json_out=False, debug=False,
    )

    content = baton.read_text()
    assert "<!-- session-kit-chain" in content
    assert f"session_id: {sid}" in content
    assert "chain_id: block-test" in content
    assert "chain_position: 1" in content


def test_no_chain_block_flag_suppresses(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    baton = project_cwd / ".stoobz" / "CONTEXT_FOR_NEXT_SESSION.md"

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    assert "session-kit-chain" not in baton.read_text()


def test_chain_block_idempotent_on_existing_block(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    baton = project_cwd / ".stoobz" / "CONTEXT_FOR_NEXT_SESSION.md"
    # Pre-seed a block tagged with this session_id
    baton.write_text(
        baton.read_text()
        + f"\n<!-- session-kit-chain\nchain_id: prior\nsession_id: {sid}\nchain_position: 1\n-->\n"
    )
    result = pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=None, chain_id_override=None, no_chain_block=False,
        json_out=False, debug=False,
    )
    assert result["chain_block_status"] == "already-present"
    # Only one chain block in the file
    assert baton.read_text().count("session-kit-chain") == 1


# --- Tag handling ---------------------------------------------------------


def _set_existing_tags(sk_root: Path, sid: str, tags: list[str]) -> None:
    manifest_path = sk_root / "manifest.json"
    m = json.loads(manifest_path.read_text())
    for s in m["sessions"]:
        if s.get("session_id") == sid:
            s["tags"] = list(tags)
    manifest_path.write_text(json.dumps(m, indent=2, sort_keys=True))


def test_park_finalize_merges_tags(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    """Pre-existing ["foo","bar"] + --tags "bar,baz" → ["foo","bar","baz"] (deduped, order preserved)."""
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    _set_existing_tags(sk_root, sid, ["foo", "bar"])

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=["bar", "baz"], chain_id_override=None,
        no_chain_block=True, json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["tags"] == ["foo", "bar", "baz"]


def test_park_finalize_empty_existing_tags(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    """Pre-existing [] + --tags "a,b,c" → ["a","b","c"]."""
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    _set_existing_tags(sk_root, sid, [])

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=["a", "b", "c"], chain_id_override=None,
        no_chain_block=True, json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["tags"] == ["a", "b", "c"]


def test_park_finalize_no_tags_arg_preserves_existing(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    """Pre-existing ["x","y"] + --tags omitted (None) → ["x","y"] (no change)."""
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    _set_existing_tags(sk_root, sid, ["x", "y"])

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["tags"] == ["x", "y"]


def test_park_finalize_empty_tags_arg_preserves_existing(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    """Pre-existing ["x"] + --tags "" (parsed to []) → ["x"]. Empty CSV is a no-op,
    matching sk write-artifact --tags semantics."""
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    _set_existing_tags(sk_root, sid, ["x"])

    pf_mod.run_park_finalize(
        cwd=project_cwd, label="x", summary="x",
        tags=[], chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    entry = _entry_for(sk_root, sid)
    assert entry["tags"] == ["x"]


# --- --json output shape --------------------------------------------------


def test_cli_json_output_shape(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)

    result = runner.invoke(
        app,
        ["park-finalize", "--label", "lbl", "--summary", "x",
         "--tags", "a,b", "--no-chain-block", "--json"],
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert set(payload).issuperset({
        "session_id", "status", "archive_path", "archive_id",
        "label", "summary", "tags", "artifacts", "missing_artifacts",
        "chain_id", "chain_position", "chain_block_status",
        "chain_block_error", "manifest",
    })
    assert payload["status"] == "archived"
    assert payload["label"] == "lbl"
    assert payload["tags"] == ["a", "b"]


# --- Idempotent re-park ---------------------------------------------------


def test_idempotent_re_park_already_archived_noop(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    sid, _ = mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    first = pf_mod.run_park_finalize(
        cwd=project_cwd, label="first", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    # Second invocation — same session, already archived
    second = pf_mod.run_park_finalize(
        cwd=project_cwd, label="second", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    assert second["status"] == "already-archived"
    # Manifest still reflects first park
    entry = _entry_for(sk_root, sid)
    assert entry["label"] == "first"
    # Archive dir from first park still present
    assert Path(first["archive_path"]).is_dir()


def test_cli_already_archived_exits_zero(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    pf_mod.run_park_finalize(
        cwd=project_cwd, label="first", summary="x",
        tags=None, chain_id_override=None, no_chain_block=True,
        json_out=False, debug=False,
    )
    result = runner.invoke(
        app,
        ["park-finalize", "--label", "second", "--summary", "x", "--no-chain-block"],
    )
    assert result.exit_code == EXIT_OK
    assert "already archived" in result.stderr


# --- Edge: no active dir --------------------------------------------------


def test_no_active_dir_is_durability_failure(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    # No checkin / write-artifact has run; active dir never created.
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["park-finalize", "--label", "x", "--summary", "x", "--no-chain-block"],
    )
    assert result.exit_code == EXIT_DURABILITY_FAIL


# --- Edge: usage errors ---------------------------------------------------


def test_cli_empty_label_usage_error(
    sk_root, fake_home, project_cwd, mock_jsonl_session
):
    mock_jsonl_session()
    _write_tldr_relay_hone(project_cwd)
    result = runner.invoke(
        app,
        ["park-finalize", "--label", "  ", "--summary", "x", "--no-chain-block"],
    )
    assert result.exit_code == EXIT_USAGE
