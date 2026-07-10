"""Unit tests for sk write-artifact.

Covers durable write + verify, ledger append, nested rel-paths, mirror
success/failure handling, and the --content-stdin / --content-file inputs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from session_kit import write_artifact as wa_mod
from session_kit.__main__ import app
from session_kit.common import EXIT_DURABILITY_FAIL, EXIT_OK, EXIT_USAGE, EXIT_WARN

runner = CliRunner()


def _ledger(active_dir: Path) -> dict:
    return json.loads((active_dir / ".session-artifacts.json").read_text())


# --- Durable write path ---------------------------------------------------


def test_basic_write_archive_and_mirror(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="tldr",
        rel_path="TLDR.md",
        content="# tldr body\n",
        mirror=True,
        json_out=False,
    )
    assert Path(r["archive_path"]).read_text() == "# tldr body\n"
    assert Path(r["mirror_path"]).read_text() == "# tldr body\n"
    assert r["mirror_status"] == "ok"
    led = _ledger(Path(r["archive_path"]).parent)
    assert led["artifacts"][-1]["name"] == "TLDR.md"
    assert led["artifacts"][-1]["skill"] == "tldr"
    assert led["artifacts"][-1]["size_bytes"] > 0


def test_no_mirror_skips_cwd_write(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="tldr",
        rel_path="TLDR.md",
        content="body\n",
        mirror=False,
        json_out=False,
    )
    assert r["mirror_status"] == "skipped"
    assert not (project_cwd / ".stoobz" / "TLDR.md").exists()


def test_nested_rel_path_creates_parents(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="rca",
        rel_path="rca/evidence/screenshot.txt",
        content="png-bytes-here",
        mirror=True,
        json_out=False,
    )
    assert Path(r["archive_path"]).read_text() == "png-bytes-here"
    assert (project_cwd / ".stoobz" / "rca" / "evidence" / "screenshot.txt").read_text() == "png-bytes-here"
    led = _ledger(Path(r["archive_path"]).parent.parent.parent)
    # Active dir is the artifact's parent up by however many segments
    # Recompute: archive_path = active_dir / rca/evidence/screenshot.txt
    archive_path = Path(r["archive_path"])
    active_dir = archive_path.parents[2]
    led = _ledger(active_dir)
    assert led["artifacts"][-1]["name"] == "rca/evidence/screenshot.txt"


def test_ledger_append_only(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    for i in range(3):
        wa_mod.run_write_artifact(
            cwd=project_cwd,
            skill="tldr",
            rel_path="TLDR.md",
            content=f"body v{i}\n",
            mirror=False,
            json_out=False,
        )
    # All three writes appear, in order
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="tldr",
        rel_path="TLDR.md",
        content="body v3\n",
        mirror=False,
        json_out=False,
    )
    led = _ledger(Path(r["archive_path"]).parent)
    names = [e["name"] for e in led["artifacts"]]
    assert names == ["TLDR.md", "TLDR.md", "TLDR.md", "TLDR.md"]
    # File contents reflect the latest write (overwrite-in-place)
    assert Path(r["archive_path"]).read_text() == "body v3\n"


def test_skills_used_records_invoking_skill(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="tldr",
        rel_path="TLDR.md",
        content="body\n",
        mirror=False,
        json_out=False,
    )
    m = json.loads((sk_root / "manifest.json").read_text())
    assert m["sessions"][0]["skills_used"] == ["tldr"]


# --- CLI surface (stdin / args / json) -------------------------------------


def test_cli_stdin_input(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "tldr", "--artifact", "TLDR.md", "--content-stdin", "--json"],
        input="from stdin\n",
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert Path(payload["archive_path"]).read_text() == "from stdin\n"


def test_cli_content_file_input(sk_root, fake_home, project_cwd, mock_jsonl_session, tmp_path):
    mock_jsonl_session()
    src = tmp_path / "src.md"
    src.write_text("from file\n")
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "tldr", "--artifact", "TLDR.md",
         "--content-file", str(src), "--json"],
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert Path(payload["archive_path"]).read_text() == "from file\n"


def test_cli_usage_error_when_no_content_source(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app, ["write-artifact", "--skill", "tldr", "--artifact", "TLDR.md"]
    )
    assert result.exit_code == EXIT_USAGE


def test_cli_usage_error_absolute_rel_path(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "tldr", "--artifact", "/etc/passwd",
         "--content-stdin"],
        input="x\n",
    )
    assert result.exit_code == EXIT_USAGE


def test_cli_usage_error_dotdot_rel_path(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "tldr", "--artifact", "../escape.md",
         "--content-stdin"],
        input="x\n",
    )
    assert result.exit_code == EXIT_USAGE


# --- Mirror failure handling ----------------------------------------------


def test_mirror_failure_warns_but_durable_succeeds(sk_root, fake_home, project_cwd, mock_jsonl_session, monkeypatch):
    mock_jsonl_session()

    import shutil
    real_copyfile = shutil.copyfile

    def boom(src, dst, *args, **kwargs):
        raise OSError("simulated mirror failure")

    monkeypatch.setattr("session_kit.write_artifact.shutil.copyfile", boom)

    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="tldr",
        rel_path="TLDR.md",
        content="body\n",
        mirror=True,
        json_out=False,
    )
    assert r["mirror_status"] == "failed"
    # Archive is intact
    assert Path(r["archive_path"]).read_text() == "body\n"
    # Ledger entry still landed
    led = _ledger(Path(r["archive_path"]).parent)
    assert led["artifacts"][-1]["name"] == "TLDR.md"


def test_cli_mirror_failure_exits_warn(sk_root, fake_home, project_cwd, mock_jsonl_session, monkeypatch):
    mock_jsonl_session()
    monkeypatch.setattr("session_kit.write_artifact.shutil.copyfile",
                        lambda *a, **kw: (_ for _ in ()).throw(OSError("simulated")))
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "tldr", "--artifact", "TLDR.md", "--content-stdin"],
        input="body\n",
    )
    assert result.exit_code == EXIT_WARN


# --- Tags propagation -----------------------------------------------------


def _manifest_entry(sk_root: Path) -> dict:
    m = json.loads((sk_root / "manifest.json").read_text())
    assert m["sessions"], "expected at least one manifest entry"
    return m["sessions"][0]


def test_tags_appends_to_empty_tags_array(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="runbook.md",
        content="body\n",
        mirror=False,
        json_out=False,
        tags=["deployment", "infrastructure"],
    )
    assert _manifest_entry(sk_root)["tags"] == ["deployment", "infrastructure"]


def test_tags_merges_and_dedupes_with_existing(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="a.md",
        content="x\n",
        mirror=False,
        json_out=False,
        tags=["alpha", "beta"],
    )
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="b.md",
        content="x\n",
        mirror=False,
        json_out=False,
        tags=["beta", "gamma"],
    )
    assert _manifest_entry(sk_root)["tags"] == ["alpha", "beta", "gamma"]


def test_tags_omitted_leaves_existing_untouched(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="a.md",
        content="x\n",
        mirror=False,
        json_out=False,
        tags=["alpha"],
    )
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="b.md",
        content="x\n",
        mirror=False,
        json_out=False,
        # no tags argument
    )
    assert _manifest_entry(sk_root)["tags"] == ["alpha"]


def test_tags_empty_csv_treated_as_no_tags(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="a.md",
        content="x\n",
        mirror=False,
        json_out=False,
        tags=["alpha"],
    )
    # Empty list mimics what _parse_tags_csv("") returns.
    wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="persist",
        rel_path="b.md",
        content="x\n",
        mirror=False,
        json_out=False,
        tags=[],
    )
    assert _manifest_entry(sk_root)["tags"] == ["alpha"]


def test_tags_sequential_calls_union_is_deduped(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    for batch in (["a", "b"], ["b", "c"], ["c", "d"], ["a"]):
        wa_mod.run_write_artifact(
            cwd=project_cwd,
            skill="persist",
            rel_path=f"art-{'-'.join(batch)}.md",
            content="x\n",
            mirror=False,
            json_out=False,
            tags=batch,
        )
    assert _manifest_entry(sk_root)["tags"] == ["a", "b", "c", "d"]


def test_parse_tags_csv_dedupes_and_strips():
    assert wa_mod._parse_tags_csv("a, b,a , c") == ["a", "b", "c"]
    assert wa_mod._parse_tags_csv("") == []
    assert wa_mod._parse_tags_csv(None) == []
    assert wa_mod._parse_tags_csv("   ,  ") == []


def test_cli_tags_flag_appends_to_manifest(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "persist", "--artifact", "x.md",
         "--content-stdin", "--no-mirror", "--tags", "alpha,beta", "--json"],
        input="body\n",
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["tags_added"] == ["alpha", "beta"]
    assert _manifest_entry(sk_root)["tags"] == ["alpha", "beta"]


def test_cli_tags_flag_omitted_no_tags_on_manifest(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "persist", "--artifact", "x.md",
         "--content-stdin", "--no-mirror"],
        input="body\n",
    )
    assert result.exit_code == EXIT_OK, result.stdout + result.stderr
    assert _manifest_entry(sk_root)["tags"] == []

# --- Content lint (warn-only) ----------------------------------------------


def test_lint_flags_adr_and_map_references(sk_root, fake_home, project_cwd, mock_jsonl_session, capsys):
    mock_jsonl_session()
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="relay",
        rel_path="CONTEXT_FOR_NEXT_SESSION.md",
        content="Per ADR-0008 the sidecar rule applies.\nSee MAP.md for edges.\n",
        mirror=True,
        json_out=False,
    )
    err = capsys.readouterr().err
    assert "lint:" in err
    assert "ADR-0008" in err
    assert "MAP.md" in err
    # warn-only: write still landed, both copies intact
    assert Path(r["archive_path"]).exists()
    assert r["mirror_status"] == "ok"
    assert len(r["lint_warnings"]) == 2


def test_lint_flags_new_index_name(sk_root, fake_home, project_cwd, mock_jsonl_session, capsys):
    mock_jsonl_session()
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="relay",
        rel_path="CONTEXT_FOR_NEXT_SESSION.md",
        content="Edges are recorded in operator/INDEX.md on the kb side.\n",
        mirror=False,
        json_out=False,
    )
    err = capsys.readouterr().err
    assert "operator/INDEX.md" in err
    assert len(r["lint_warnings"]) == 1


def test_lint_flags_blocklist_prefixes_in_all_forms(
    sk_root, fake_home, project_cwd, mock_jsonl_session, capsys, monkeypatch
):
    monkeypatch.setenv("PORTABLE_REFS_BLOCKLIST", "~/.private-kb")
    mock_jsonl_session()
    home = str(Path.home())
    content = (
        f"literal ~/.private-kb/patterns/x.md\n"
        f"expanded {home}/.private-kb/decisions/y.md\n"
        "dollar $HOME/.private-kb/conventions/z.md\n"
        "clean line\n"
    )
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="relay",
        rel_path="CONTEXT_FOR_NEXT_SESSION.md",
        content=content,
        mirror=False,
        json_out=False,
    )
    err = capsys.readouterr().err
    assert "blocklisted path prefix" in err
    assert len(r["lint_warnings"]) == 3


def test_lint_silent_on_clean_content(sk_root, fake_home, project_cwd, mock_jsonl_session, capsys):
    mock_jsonl_session()
    r = wa_mod.run_write_artifact(
        cwd=project_cwd,
        skill="tldr",
        rel_path="TLDR.md",
        content="# Findings\nAll clean here.\n",
        mirror=False,
        json_out=False,
    )
    err = capsys.readouterr().err
    assert "lint:" not in err
    assert r["lint_warnings"] == []


def test_lint_never_changes_exit_code(sk_root, fake_home, project_cwd, mock_jsonl_session):
    mock_jsonl_session()
    result = runner.invoke(
        app,
        ["write-artifact", "--skill", "relay", "--artifact", "R.md", "--content-stdin"],
        input="mentions ADR-0001\n",
    )
    assert result.exit_code == EXIT_OK
