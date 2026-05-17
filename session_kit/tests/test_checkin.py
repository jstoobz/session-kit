"""Unit tests for sk checkin.

Covers the three resolution tiers, first-checkin vs re-entry, JSON output,
skills_used append rules per mode, last_exchange real-user filter, and the
write-once / liveness-refresh discipline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from session_kit import checkin as checkin_mod
from session_kit.__main__ import app
from session_kit.common import EXIT_DURABILITY_FAIL, EXIT_OK, EXIT_USAGE

runner = CliRunner()


def _load_manifest(sk_root: Path) -> dict:
    return json.loads((sk_root / "manifest.json").read_text())


def _load_ledger(active_dir: Path) -> dict:
    return json.loads((active_dir / ".session-artifacts.json").read_text())


# --- Tier resolution -------------------------------------------------------


def test_tier1_jsonl_resolution(sk_root, fake_home, project_cwd, mock_jsonl_session):
    sid, _ = mock_jsonl_session()
    result = checkin_mod.run_checkin(
        cwd=project_cwd, mode="explicit", invoking=None, json_out=False, debug=False
    )
    assert result["session_id"] == sid
    assert result["resolved_via"] == "jsonl"
    assert result["is_first"] is True
    assert Path(result["active_dir"]).is_dir()
    assert Path(result["ledger"]).is_file()


def test_tier3_synthesis_when_no_jsonl(sk_root, fake_home, project_cwd):
    # No JSONL file written; expect tier-3 synthesis.
    result = checkin_mod.run_checkin(
        cwd=project_cwd, mode="explicit", invoking=None, json_out=False, debug=False
    )
    assert result["resolved_via"] == "synthesized"
    cache = project_cwd / ".stoobz" / ".session-id"
    assert cache.is_file()
    assert cache.read_text().strip() == result["session_id"]


def test_tier3_cached_reused(sk_root, fake_home, project_cwd):
    # First call synthesizes; second call should be cached.
    r1 = checkin_mod.run_checkin(
        cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False
    )
    r2 = checkin_mod.run_checkin(
        cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False
    )
    assert r1["session_id"] == r2["session_id"]
    assert r2["resolved_via"] == "cached"


# --- First-checkin vs re-entry ---------------------------------------------


def test_first_then_reentry(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    r1 = checkin_mod.run_checkin(
        cwd=project_cwd, mode="explicit", invoking=None, json_out=False, debug=False
    )
    assert r1["is_first"] is True
    r2 = checkin_mod.run_checkin(
        cwd=project_cwd, mode="explicit", invoking=None, json_out=False, debug=False
    )
    assert r2["is_first"] is False
    assert r1["session_id"] == r2["session_id"]


def test_reentry_does_not_modify_ledger_metadata(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    r1 = checkin_mod.run_checkin(
        cwd=project_cwd, mode="silent", invoking="tldr", json_out=False, debug=False
    )
    led1 = _load_ledger(Path(r1["active_dir"]))
    # Hand-edit the ledger to simulate an artifact write
    led1["artifacts"].append({"name": "manual.md", "size_bytes": 1})
    (Path(r1["ledger"])).write_text(json.dumps(led1, indent=2, sort_keys=True))

    r2 = checkin_mod.run_checkin(
        cwd=project_cwd, mode="silent", invoking="tldr", json_out=False, debug=False
    )
    led2 = _load_ledger(Path(r2["active_dir"]))
    assert led2["artifacts"] == led1["artifacts"]
    # Write-once metadata unchanged
    assert led2["session_id"] == led1["session_id"]
    assert led2["started_at"] == led1["started_at"]
    assert led2["source_dir"] == led1["source_dir"]


def test_reentry_refreshes_last_activity(sk_root, fake_home, project_cwd, mock_jsonl_session, monkeypatch):
    mock_jsonl_session()
    ts = iter(["2026-05-17T10:00:00Z", "2026-05-17T11:00:00Z"])
    monkeypatch.setattr(checkin_mod, "now_iso", lambda: next(ts))
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False)
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False)
    m = _load_manifest(sk_root)
    entry = m["sessions"][0]
    assert entry["last_activity"] == "2026-05-17T11:00:00Z"


# --- skills_used append rules ---------------------------------------------


def test_explicit_appends_checkin(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    checkin_mod.run_checkin(
        cwd=project_cwd, mode="explicit", invoking=None, json_out=False, debug=False
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["skills_used"] == ["checkin"]


def test_silent_with_invoking_appends_skill(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    checkin_mod.run_checkin(
        cwd=project_cwd, mode="silent", invoking="tldr", json_out=False, debug=False
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["skills_used"] == ["tldr"]


def test_silent_without_invoking_appends_nothing(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    checkin_mod.run_checkin(
        cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["skills_used"] == []


def test_explicit_ignores_invoking(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    checkin_mod.run_checkin(
        cwd=project_cwd, mode="explicit", invoking="relay", json_out=False, debug=False
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["skills_used"] == ["checkin"]


def test_skills_used_dedupes(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    for _ in range(3):
        checkin_mod.run_checkin(
            cwd=project_cwd, mode="silent", invoking="tldr", json_out=False, debug=False
        )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["skills_used"] == ["tldr"]


def test_skills_used_preserves_order(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    checkin_mod.run_checkin(cwd=project_cwd, mode="explicit", invoking=None, json_out=False, debug=False)
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking="tldr", json_out=False, debug=False)
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking="relay", json_out=False, debug=False)
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["skills_used"] == ["checkin", "tldr", "relay"]


# --- last_exchange real-user filter ----------------------------------------


def test_last_exchange_filters_synthetic_user_records(sk_root, fake_home, project_cwd, mock_jsonl_session):
    sid, _ = mock_jsonl_session(records=[
        {"type": "user", "timestamp": "2026-05-17T10:00:00Z",
         "message": {"content": "real hello"}},
        {"type": "assistant", "timestamp": "2026-05-17T10:00:05Z",
         "message": {"content": [{"type": "text", "text": "real reply"}]}},
        # isMeta — should be ignored (skill-launch injection)
        {"type": "user", "timestamp": "2026-05-17T10:01:00Z",
         "isMeta": True,
         "message": {"content": "<command-name>/foo</command-name>"}},
        # isSidechain — should be ignored
        {"type": "user", "timestamp": "2026-05-17T10:02:00Z",
         "isSidechain": True,
         "message": {"content": "subagent prompt"}},
        # tool_result content — should be ignored
        {"type": "user", "timestamp": "2026-05-17T10:03:00Z",
         "message": {"content": [{"type": "tool_result", "content": "..."}]}},
    ])
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False)
    entry = _load_manifest(sk_root)["sessions"][0]
    le = entry["last_exchange"]
    assert le is not None
    assert le["user"]["text"] == "real hello"
    assert le["assistant"]["text"] == "real reply"


def test_last_exchange_truncates_at_80_chars(sk_root, fake_home, project_cwd, mock_jsonl_session):
    long_text = "a" * 200
    mock_jsonl_session(records=[
        {"type": "user", "timestamp": "2026-05-17T10:00:00Z",
         "message": {"content": long_text}},
    ])
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False)
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["last_exchange"]["user"]["text"] == "a" * 80 + "..."


def test_last_exchange_null_when_no_jsonl(sk_root, fake_home, project_cwd):
    checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False)
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["last_exchange"] is None


# --- Ledger initial content ------------------------------------------------


def test_ledger_initial_content(sk_root, fake_home, project_cwd, mock_jsonl_session):
    sid, _ = mock_jsonl_session(records=[
        {"type": "user", "timestamp": "2026-05-17T09:00:00Z",
         "message": {"content": "hi"}},
    ])
    r = checkin_mod.run_checkin(cwd=project_cwd, mode="silent", invoking=None, json_out=False, debug=False)
    led = _load_ledger(Path(r["active_dir"]))
    assert led["schema_version"] == 1
    assert led["session_id"] == sid
    assert led["started_at"] == "2026-05-17T09:00:00Z"
    assert led["source_dir"] == str(project_cwd)
    assert led["artifacts"] == []


# --- JSON output -----------------------------------------------------------


def test_json_output_shape(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(app, ["checkin", "--explicit", "--json"])
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert set(payload).issuperset({
        "session_id", "active_dir", "ledger", "manifest", "resolved_via",
        "is_first", "mode", "appended_skill",
    })
    assert payload["mode"] == "explicit"
    assert payload["appended_skill"] == "checkin"


# --- Exit codes ------------------------------------------------------------


def test_usage_error_both_modes(sk_root, fake_home, project_cwd):
    result = runner.invoke(app, ["checkin", "--explicit", "--silent"])
    assert result.exit_code == EXIT_USAGE


def test_durability_failure_on_unwriteable_root(sk_root, fake_home, project_cwd, monkeypatch):
    # Point SESSION_KIT_ROOT at a path that cannot be created (under /dev/null/...).
    monkeypatch.setenv("SESSION_KIT_ROOT", "/dev/null/cant-create-this")
    result = runner.invoke(app, ["checkin", "--explicit"])
    assert result.exit_code == EXIT_DURABILITY_FAIL


# --- Chain inheritance flags -----------------------------------------------


def _write_baton(
    cwd: Path,
    *,
    chain_id: str | None = "demo-chain",
    session_id: str = "11111111-1111-1111-1111-111111111111",
    chain_position: int = 1,
    parent_chain_id: str | None = None,
    checkpoint_nodes: list[int] | str | None = None,
    body_prefix: str = "# Relay baton body\n",
    filename: str = "CONTEXT_FOR_NEXT_SESSION.md",
) -> Path:
    stoobz = cwd / ".stoobz"
    stoobz.mkdir(parents=True, exist_ok=True)
    lines = ["<!-- session-kit-chain"]
    lines.append(f"chain_id: {chain_id if chain_id is not None else 'null'}")
    lines.append(f"session_id: {session_id}")
    lines.append(f"chain_position: {chain_position}")
    if parent_chain_id is not None:
        lines.append(f"parent_chain_id: {parent_chain_id}")
    if checkpoint_nodes is not None:
        if isinstance(checkpoint_nodes, list):
            nodes_value = json.dumps(checkpoint_nodes)
        else:
            nodes_value = checkpoint_nodes
        lines.append(f"checkpoint_nodes: {nodes_value}")
    lines.append("-->\n")
    block = "\n".join(lines)
    path = stoobz / filename
    path.write_text(body_prefix + "\n" + block, encoding="utf-8")
    return path


def test_first_checkin_individual_chain_flags(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        [
            "checkin",
            "--explicit",
            "--chain-id", "alpha-chain",
            "--previous-session-id", "prev-sid-1",
            "--chain-position", "4",
            "--parent-chain-id", "root-chain",
            "--checkpoint-nodes", "1,3,5",
        ],
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] == "alpha-chain"
    assert entry["previous_session_id"] == "prev-sid-1"
    assert entry["chain_position"] == 4
    assert entry["parent_chain_id"] == "root-chain"
    assert entry["checkpoint_nodes"] == [1, 3, 5]


def test_first_checkin_inherit_chain_from_baton(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    baton = _write_baton(
        project_cwd,
        chain_id="sk-rewrite-validation",
        session_id="c3ee5c2b-aaaa-bbbb-cccc-deadbeefcafe",
        chain_position=1,
    )
    result = runner.invoke(
        app, ["checkin", "--silent", "--invoking", "pickup", "--inherit-chain-from", str(baton)]
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] == "sk-rewrite-validation"
    assert entry["previous_session_id"] == "c3ee5c2b-aaaa-bbbb-cccc-deadbeefcafe"
    assert entry["chain_position"] == 2
    assert entry["parent_chain_id"] is None
    assert entry["checkpoint_nodes"] is None


def test_first_checkin_inherit_missing_path_silent_fallthrough(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    bogus = project_cwd / ".stoobz" / "does-not-exist.md"
    result = runner.invoke(
        app, ["checkin", "--silent", "--inherit-chain-from", str(bogus)]
    )
    assert result.exit_code == EXIT_OK
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] is None
    assert entry["chain_position"] is None
    assert entry["previous_session_id"] is None


def test_first_checkin_inherit_baton_with_no_chain_block(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    stoobz = project_cwd / ".stoobz"
    stoobz.mkdir(parents=True, exist_ok=True)
    baton = stoobz / "CONTEXT_FOR_NEXT_SESSION.md"
    baton.write_text("# Legacy relay baton\n\nNo chain block here.\n", encoding="utf-8")

    result = runner.invoke(
        app, ["checkin", "--silent", "--inherit-chain-from", str(baton)]
    )
    assert result.exit_code == EXIT_OK
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] is None
    assert entry["chain_position"] is None
    assert entry["previous_session_id"] is None


def test_first_checkin_inherit_checkpoint_baton_full_fields(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    baton = _write_baton(
        project_cwd,
        chain_id="branched-chain",
        session_id="abc-parked-sid",
        chain_position=2,
        parent_chain_id="root-chain",
        checkpoint_nodes=[1, 2, 4],
    )
    result = runner.invoke(
        app, ["checkin", "--silent", "--invoking", "pickup", "--inherit-chain-from", str(baton)]
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] == "branched-chain"
    assert entry["previous_session_id"] == "abc-parked-sid"
    assert entry["chain_position"] == 3
    assert entry["parent_chain_id"] == "root-chain"
    assert entry["checkpoint_nodes"] == [1, 2, 4]


def test_reentry_preserves_chain_fields_and_ignores_args(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    runner.invoke(
        app,
        [
            "checkin",
            "--silent",
            "--chain-id", "first-chain",
            "--chain-position", "2",
            "--previous-session-id", "first-prev",
        ],
    )
    # Re-entry with different chain args — must NOT overwrite.
    runner.invoke(
        app,
        [
            "checkin",
            "--silent",
            "--chain-id", "rewrite-attempt",
            "--chain-position", "99",
            "--previous-session-id", "rewrite-prev",
        ],
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] == "first-chain"
    assert entry["chain_position"] == 2
    assert entry["previous_session_id"] == "first-prev"


def test_chain_id_flag_overrides_inherit_chain_from(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    baton = _write_baton(
        project_cwd,
        chain_id="from-baton",
        session_id="baton-sid",
        chain_position=1,
    )
    runner.invoke(
        app,
        [
            "checkin",
            "--silent",
            "--inherit-chain-from", str(baton),
            "--chain-id", "explicit-wins",
        ],
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] == "explicit-wins"
    # Other inherited fields still populate from the baton.
    assert entry["previous_session_id"] == "baton-sid"
    assert entry["chain_position"] == 2


def test_checkpoint_nodes_parses_csv_to_int_list(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    runner.invoke(
        app, ["checkin", "--silent", "--checkpoint-nodes", "1,2,4"]
    )
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["checkpoint_nodes"] == [1, 2, 4]


def test_checkpoint_nodes_rejects_non_numeric_tokens(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app, ["checkin", "--silent", "--checkpoint-nodes", "bad,csv"]
    )
    assert result.exit_code == EXIT_USAGE


# --- Chain block parser: prose-leak resilience ----------------------------


def test_chain_block_after_prose_mention():
    body = (
        "# Relay baton body\n"
        "\n"
        "See the <!-- session-kit-chain ... --> block at the bottom for the\n"
        "machine-readable chain state.\n"
        "\n"
        "<!-- session-kit-chain\n"
        "chain_id: real-chain\n"
        "session_id: aaaa-bbbb-cccc-dddd\n"
        "chain_position: 3\n"
        "-->\n"
    )
    parsed = checkin_mod._parse_chain_block(body)
    assert parsed == {
        "chain_id": "real-chain",
        "session_id": "aaaa-bbbb-cccc-dddd",
        "chain_position": "3",
    }


def test_multiple_real_chain_blocks_takes_last():
    body = (
        "<!-- session-kit-chain\n"
        "chain_id: first-chain\n"
        "session_id: sid-1\n"
        "chain_position: 1\n"
        "-->\n"
        "\n"
        "<!-- session-kit-chain\n"
        "chain_id: second-chain\n"
        "session_id: sid-2\n"
        "chain_position: 2\n"
        "-->\n"
    )
    parsed = checkin_mod._parse_chain_block(body)
    assert parsed == {
        "chain_id": "second-chain",
        "session_id": "sid-2",
        "chain_position": "2",
    }


def test_prose_only_returns_none():
    body = (
        "# Relay baton body\n"
        "\n"
        "The <!-- session-kit-chain ... --> marker is documented in /relay's\n"
        "SKILL.md but no real block is present.\n"
    )
    assert checkin_mod._parse_chain_block(body) is None


def test_inherit_chain_from_with_prose_leak_baton(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    stoobz = project_cwd / ".stoobz"
    stoobz.mkdir(parents=True, exist_ok=True)
    baton = stoobz / "CONTEXT_FOR_NEXT_SESSION.md"
    baton.write_text(
        "# Relay baton body\n"
        "\n"
        "See the <!-- session-kit-chain ... --> block at the bottom for the\n"
        "machine-readable chain state.\n"
        "\n"
        "<!-- session-kit-chain\n"
        "chain_id: chain-inheritance-smoke-test\n"
        "session_id: bf7e0a76-ad7b-464a-b0b7-dad053ca3952\n"
        "chain_position: 1\n"
        "-->\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["checkin", "--silent", "--invoking", "pickup", "--inherit-chain-from", str(baton)]
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    entry = _load_manifest(sk_root)["sessions"][0]
    assert entry["chain_id"] == "chain-inheritance-smoke-test"
    assert entry["previous_session_id"] == "bf7e0a76-ad7b-464a-b0b7-dad053ca3952"
    assert entry["chain_position"] == 2
