"""Unit tests for session_kit.common helpers."""
from pathlib import Path

from session_kit.common import encode_path, resolve_session_id


class TestEncodePath:
    def test_plain_path_slashes_become_dashes(self):
        assert encode_path(Path("/Users/me/repos/tool")) == "-Users-me-repos-tool"

    def test_dot_directories_encode_to_double_dash(self):
        # Claude Code encodes every non-alphanumeric char, so a dot-dir
        # produces a double dash. A slash-only encoder computed
        # `-Users-me-.stoobz-kb` here — a directory that never exists —
        # which broke tier-1/2 session-id resolution for any project
        # living under a dot-directory.
        assert encode_path(Path("/Users/me/.stoobz/kb")) == "-Users-me--stoobz-kb"

    def test_underscores_and_dots_in_names(self):
        assert encode_path(Path("/tmp/my_proj/v1.2")) == "-tmp-my-proj-v1-2"


class TestResolveSessionIdEncoding:
    def test_tier1_hits_dot_dir_project(self, tmp_path, monkeypatch):
        # cwd lives under a dot-directory; the encoded projects dir must be
        # found (tier 1), not fall through to the tier-3 cache.
        home = tmp_path
        cwd = home / ".stoobz" / "kb"
        cwd.mkdir(parents=True)
        encoded = encode_path(cwd)
        proj_dir = home / ".claude" / "projects" / encoded
        proj_dir.mkdir(parents=True)
        (proj_dir / "11111111-2222-3333-4444-555555555555.jsonl").write_text(
            "{}\n", encoding="utf-8"
        )
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        res = resolve_session_id(cwd)

        assert res.resolved_via == "jsonl"
        assert res.session_id == "11111111-2222-3333-4444-555555555555"
