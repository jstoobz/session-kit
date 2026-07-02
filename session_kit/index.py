"""sk index — search the manifest and surface session artifacts.

Read-side companion to `sk checkin` (the WAL-style registration write). The
manifest entries that `sk checkin` registers as `status: "active"` show up here
under `--active`; finalized entries show up by default. `--orphans` scans the
filesystem for `<sid>-active/` directories that have no manifest entry — the
bridge for legacy sessions that never registered (registered-but-stalled
entries are a different concern and not handled here).

Supports:
  * default       — archived sessions, newest first (table)
  * --active      — active sessions (ACTIVE badge)
  * --orphans     — filesystem-only active dirs not in manifest
  * --chain       — group by chain_id, sorted by chain_position
  * --since       — date filter (today | week | month | YYYY-MM-DD)
  * --deep <pat>  — grep through archived artifact text
  * --json        — structured output
  * <filter>      — positional substring filter across tags / summary / label /
                    project / branch / session_id / chain_id / last_exchange
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

import typer

from .common import (
    EXIT_OK,
    EXIT_USAGE,
    session_kit_root,
)


# --- Data loading -----------------------------------------------------------


def _load_manifest_sessions(manifest_path: Path) -> list[dict]:
    if not manifest_path.is_file():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return list(data.get("sessions") or [])


def _is_active(entry: dict) -> bool:
    return entry.get("status") == "active"


def _is_archived(entry: dict) -> bool:
    return entry.get("status") != "active"


# --- Filtering --------------------------------------------------------------


_FILTER_FIELDS = (
    "tags",
    "summary",
    "label",
    "project",
    "branch",
    "session_id",
    "chain_id",
)


def _entry_search_haystack(entry: dict) -> str:
    parts: list[str] = []
    for f in _FILTER_FIELDS:
        v = entry.get(f)
        if v is None:
            continue
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        else:
            parts.append(str(v))
    le = entry.get("last_exchange") or {}
    if isinstance(le, dict):
        for side in ("user", "assistant"):
            side_entry = le.get(side)
            if isinstance(side_entry, dict):
                text = side_entry.get("text")
                if text:
                    parts.append(str(text))
    return " ".join(parts).lower()


def _apply_filter(entries: list[dict], term: str | None) -> list[dict]:
    if not term:
        return entries
    needle = term.strip().lower()
    if not needle:
        return entries
    return [e for e in entries if needle in _entry_search_haystack(e)]


# --- Date helpers -----------------------------------------------------------


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _parse_since(value: str) -> datetime:
    """Convert a `--since` token to a UTC cutoff datetime.

    Accepts: today, week, month, YYYY-MM-DD.
    """
    v = value.strip().lower()
    now = datetime.now(timezone.utc)
    if v == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if v == "week":
        return now - timedelta(days=7)
    if v == "month":
        return now - timedelta(days=30)
    m = _DATE_RE.match(v)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    raise ValueError(f"unrecognized --since value: {value!r}")


def _entry_reference_dt(entry: dict) -> datetime | None:
    """Pick the freshest timestamp on the entry for `--since` comparison."""
    for key in ("last_activity", "started_at"):
        v = entry.get(key)
        if v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
    date = entry.get("date")
    if date:
        m = _DATE_RE.match(str(date))
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    return None


def _apply_since(entries: list[dict], cutoff: datetime | None) -> list[dict]:
    if cutoff is None:
        return entries
    keep: list[dict] = []
    for e in entries:
        dt = _entry_reference_dt(e)
        if dt is None:
            continue
        if dt >= cutoff:
            keep.append(e)
    return keep


# --- Sort helpers -----------------------------------------------------------


def _sort_key_archived(entry: dict) -> str:
    return entry.get("date") or ""


def _sort_key_active(entry: dict) -> str:
    return entry.get("last_activity") or entry.get("started_at") or ""


# --- Orphan discovery -------------------------------------------------------


@dataclass
class Orphan:
    project: str
    session_id: str
    active_dir: Path
    last_mtime: datetime | None
    ledger_artifact_count: int


def _scan_orphans(sk_root: Path, registered_sids: set[str]) -> list[Orphan]:
    sessions_dir = sk_root / "sessions"
    if not sessions_dir.is_dir():
        return []
    out: list[Orphan] = []
    for project_dir in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
        for active_dir in sorted(d for d in project_dir.iterdir() if d.is_dir()):
            name = active_dir.name
            if not name.endswith("-active"):
                continue
            sid = name[: -len("-active")]
            if sid in registered_sids:
                continue
            try:
                mtime = datetime.fromtimestamp(active_dir.stat().st_mtime, tz=timezone.utc)
            except OSError:
                mtime = None
            ledger = active_dir / ".session-artifacts.json"
            count = 0
            if ledger.is_file():
                try:
                    data = json.loads(ledger.read_text(encoding="utf-8"))
                    arts = data.get("artifacts") or []
                    count = len(arts) if isinstance(arts, list) else 0
                except (json.JSONDecodeError, OSError):
                    count = 0
            out.append(
                Orphan(
                    project=project_dir.name,
                    session_id=sid,
                    active_dir=active_dir,
                    last_mtime=mtime,
                    ledger_artifact_count=count,
                )
            )
    out.sort(key=lambda o: (o.last_mtime or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return out


# --- Deep search ------------------------------------------------------------


@dataclass
class DeepHit:
    archive_path: Path
    artifact: str
    line_number: int
    snippet: str


def _deep_search(sk_root: Path, pattern: str) -> list[DeepHit]:
    sessions_dir = sk_root / "sessions"
    if not sessions_dir.is_dir():
        return []
    needle = pattern.lower()
    hits: list[DeepHit] = []
    for root, _, files in os.walk(sessions_dir):
        rp = Path(root)
        for fname in files:
            if not fname.endswith(".md"):
                continue
            full = rp / fname
            try:
                with full.open("r", encoding="utf-8", errors="replace") as f:
                    for n, line in enumerate(f, start=1):
                        if needle in line.lower():
                            snippet = line.strip()
                            if len(snippet) > 160:
                                snippet = snippet[:160] + "..."
                            archive_dir, artifact_rel = _split_archive_artifact(sessions_dir, full)
                            hits.append(
                                DeepHit(
                                    archive_path=archive_dir,
                                    artifact=artifact_rel,
                                    line_number=n,
                                    snippet=snippet,
                                )
                            )
            except OSError:
                continue
    return hits


def _split_archive_artifact(sessions_dir: Path, file_path: Path) -> tuple[Path, str]:
    """Given sessions/<project>/<archive-id>/<rel-path>, return (archive_dir, rel_path)."""
    rel = file_path.relative_to(sessions_dir)
    parts = rel.parts
    if len(parts) >= 3:
        archive_dir = sessions_dir / parts[0] / parts[1]
        artifact = "/".join(parts[2:])
        return archive_dir, artifact
    return file_path.parent, file_path.name


# --- Rendering --------------------------------------------------------------


def _render_human_since(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "—"
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _last_exchange_summary(entry: dict) -> str:
    le = entry.get("last_exchange") or {}
    if not isinstance(le, dict):
        return "—"
    user = le.get("user") or {}
    asst = le.get("assistant") or {}
    user_text = (user.get("text") if isinstance(user, dict) else None) or ""
    asst_text = (asst.get("text") if isinstance(asst, dict) else None) or ""
    if not user_text and not asst_text:
        return "—"
    parts = []
    if user_text:
        parts.append(f'U: "{user_text}"')
    if asst_text:
        parts.append(f'A: "{asst_text}"')
    return " / ".join(parts)


def _artifact_badges(entry: dict) -> str:
    arts = entry.get("artifacts") or []
    flags = {
        "TLDR.md": "T",
        "CONTEXT_FOR_NEXT_SESSION.md": "C",
        "CHECKPOINT_CONTEXT.md": "K",
        "RETRO.md": "R",
        "HONE.md": "P",
        "HANDOFF.md": "H",
        "INVESTIGATION_SUMMARY.md": "I",
        "INVESTIGATION_CONTEXT.md": "I",
    }
    seen: list[str] = []
    for a in arts:
        flag = flags.get(a)
        if flag and flag not in seen:
            seen.append(flag)
    return " ".join(seen) if seen else "—"


def _render_active_table(active: list[dict], now: datetime) -> str:
    if not active:
        return ""
    lines = [
        "## Active Sessions",
        "",
        "| Project | Since | Last Active | Branch | Last Exchange | Resume |",
        "|---------|-------|-------------|--------|---------------|--------|",
    ]
    for e in sorted(active, key=_sort_key_active, reverse=True):
        proj = e.get("project") or "—"
        started = e.get("started_at")
        last = e.get("last_activity")
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00")) if started else None
        except (ValueError, AttributeError):
            started_dt = None
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00")) if last else None
        except (ValueError, AttributeError):
            last_dt = None
        since = _render_human_since(started_dt, now)
        last_render = _render_human_since(last_dt, now)
        branch = e.get("branch") or "—"
        le = _last_exchange_summary(e)
        resume = e.get("return_to") or "—"
        lines.append(f"| {proj} | {since} | {last_render} | {branch} | {le} | `{resume}` |")
    return "\n".join(lines) + "\n"


def _render_archived_table(archived: list[dict]) -> str:
    if not archived:
        return ""
    lines = [
        f"## Session Index ({len(archived)} archived sessions)",
        "",
        "| Project | Date | Label | Summary | Artifacts | Tags |",
        "|---------|------|-------|---------|-----------|------|",
    ]
    for e in sorted(archived, key=_sort_key_archived, reverse=True):
        proj = e.get("project") or "—"
        date = e.get("date") or "—"
        label = e.get("label") or "—"
        summary = e.get("summary") or "—"
        if len(summary) > 60:
            summary = summary[:60] + "..."
        badges = _artifact_badges(e)
        tags = ", ".join(e.get("tags") or []) or "—"
        lines.append(f"| {proj} | {date} | {label} | {summary} | {badges} | {tags} |")
    lines.append("")
    lines.append("**Legend:** T=TLDR C=Context K=Checkpoint R=Retro P=Hone H=Handoff I=Investigation")
    return "\n".join(lines) + "\n"


def _render_orphans(orphans: list[Orphan], now: datetime) -> str:
    if not orphans:
        return ""
    lines = [
        f"## Orphans ({len(orphans)} active dir(s) not in manifest)",
        "",
        "| Project | Session | Last Mtime | Ledger Artifacts | Active Dir |",
        "|---------|---------|------------|------------------|------------|",
    ]
    for o in orphans:
        mtime = _render_human_since(o.last_mtime, now)
        lines.append(
            f"| {o.project} | {o.session_id[:8]}... | {mtime} | {o.ledger_artifact_count} | `{o.active_dir}` |"
        )
    return "\n".join(lines) + "\n"


def _render_chain_groups(entries: list[dict], filter_term: str | None) -> str:
    """Group entries by chain_id, sort by chain_position, show chain forks."""
    chains: dict[str, list[dict]] = {}
    unchained: list[dict] = []
    for e in entries:
        cid = e.get("chain_id")
        if cid:
            chains.setdefault(cid, []).append(e)
        else:
            unchained.append(e)

    # Filter chains by chain_id, project, summary if filter_term provided.
    if filter_term:
        needle = filter_term.strip().lower()
        kept: dict[str, list[dict]] = {}
        for cid, members in chains.items():
            if needle in cid.lower():
                kept[cid] = members
                continue
            for m in members:
                hay = " ".join(
                    str(m.get(f) or "") for f in ("project", "summary", "label")
                ).lower()
                if needle in hay:
                    kept[cid] = members
                    break
        # Also include chains that fork from a matched chain.
        for cid, members in chains.items():
            if cid in kept:
                continue
            for m in members:
                parent = m.get("parent_chain_id")
                if parent and parent in kept:
                    kept[cid] = members
                    break
        chains = kept
        unchained = []  # filter excludes unchained when chain term is given

    if not chains and not unchained:
        return "## Chains\n\n(no matching chains)\n"

    out: list[str] = ["## Chains", ""]
    for cid in sorted(chains.keys(), key=lambda k: max((m.get("date") or "") for m in chains[k]), reverse=True):
        members = sorted(chains[cid], key=lambda m: m.get("chain_position") or 0)
        parent = next((m.get("parent_chain_id") for m in members if m.get("parent_chain_id")), None)
        nodes = next((m.get("checkpoint_nodes") for m in members if m.get("checkpoint_nodes")), None)
        header = f"### {cid} ({len(members)} nodes)"
        if parent:
            nodes_disp = ", ".join(str(n) for n in nodes) if nodes else "?"
            header += f"  ← forked from {parent} (nodes {nodes_disp})"
        out.append(header)
        out.append("")
        out.append("| # | Date | Project | Status | Summary |")
        out.append("|---|------|---------|--------|---------|")
        for m in members:
            pos = m.get("chain_position") or "?"
            date = m.get("date") or "—"
            proj = m.get("project") or "—"
            status = m.get("status") or "—"
            summary = m.get("summary") or m.get("label") or "—"
            if len(summary) > 60:
                summary = summary[:60] + "..."
            out.append(f"| {pos} | {date} | {proj} | {status} | {summary} |")
        out.append("")

    if unchained:
        out.append(f"### Unchained Sessions ({len(unchained)})")
        out.append("")
        out.append("| Date | Project | Label | Summary |")
        out.append("|------|---------|-------|---------|")
        for m in sorted(unchained, key=_sort_key_archived, reverse=True):
            out.append(
                f"| {m.get('date') or '—'} | {m.get('project') or '—'} | "
                f"{m.get('label') or '—'} | {m.get('summary') or '—'} |"
            )
    return "\n".join(out) + "\n"


def _render_deep_hits(hits: list[DeepHit], pattern: str) -> str:
    if not hits:
        return f"## Deep Search — \"{pattern}\" (0 hits)\n"
    by_archive: dict[Path, list[DeepHit]] = {}
    for h in hits:
        by_archive.setdefault(h.archive_path, []).append(h)
    out = [f"## Deep Search — \"{pattern}\" ({len(hits)} hits across {len(by_archive)} session(s))", ""]
    for archive in sorted(by_archive.keys()):
        out.append(f"### {archive}")
        for h in by_archive[archive]:
            out.append(f"**{h.artifact}:{h.line_number}** — {h.snippet}")
        out.append("")
    return "\n".join(out) + "\n"


# --- Top-level orchestration ------------------------------------------------


@dataclass
class IndexResult:
    active: list[dict] = field(default_factory=list)
    archived: list[dict] = field(default_factory=list)
    orphans: list[Orphan] = field(default_factory=list)
    deep_hits: list[DeepHit] = field(default_factory=list)
    chain_view: bool = False
    filter_term: str | None = None


def run_index(
    *,
    filter_term: str | None,
    active_only: bool,
    orphans_only: bool,
    chain: bool,
    since: str | None,
    deep: str | None,
    json_out: bool,
) -> IndexResult:
    sk_root = session_kit_root()
    manifest_path = sk_root / "manifest.json"
    sessions = _load_manifest_sessions(manifest_path)

    cutoff = _parse_since(since) if since else None

    active = [e for e in sessions if _is_active(e)]
    archived = [e for e in sessions if _is_archived(e)]

    active = _apply_since(active, cutoff)
    archived = _apply_since(archived, cutoff)

    if filter_term and not chain:
        active = _apply_filter(active, filter_term)
        archived = _apply_filter(archived, filter_term)

    result = IndexResult(filter_term=filter_term)

    if orphans_only:
        registered = {e.get("session_id") for e in sessions if e.get("session_id")}
        result.orphans = _scan_orphans(sk_root, registered)
        return result

    if active_only:
        result.active = active
        return result

    if chain:
        result.archived = archived + active
        result.chain_view = True
        return result

    result.active = active
    result.archived = archived

    if deep:
        result.deep_hits = _deep_search(sk_root, deep)

    return result


def _render(result: IndexResult, *, now: datetime, deep_pattern: str | None, orphans_only: bool) -> str:
    if result.chain_view:
        return _render_chain_groups(result.archived, result.filter_term)

    if orphans_only:
        if not result.orphans:
            return "## Orphans (0)\n\n(no orphaned active dirs found)\n"
        return _render_orphans(result.orphans, now)

    sections: list[str] = []
    if result.active:
        sections.append(_render_active_table(result.active, now))
    if result.archived:
        sections.append(_render_archived_table(result.archived))
    if deep_pattern is not None:
        sections.append(_render_deep_hits(result.deep_hits, deep_pattern))

    if not sections:
        return "(no sessions found)\n"
    return "\n".join(s for s in sections if s)


def _to_jsonable(result: IndexResult, deep_pattern: str | None) -> dict:
    return {
        "filter": result.filter_term,
        "active": result.active,
        "archived": result.archived,
        "orphans": [
            {
                "project": o.project,
                "session_id": o.session_id,
                "active_dir": str(o.active_dir),
                "last_mtime": o.last_mtime.isoformat() if o.last_mtime else None,
                "ledger_artifact_count": o.ledger_artifact_count,
            }
            for o in result.orphans
        ],
        "deep": {
            "pattern": deep_pattern,
            "hits": [
                {
                    "archive_path": str(h.archive_path),
                    "artifact": h.artifact,
                    "line_number": h.line_number,
                    "snippet": h.snippet,
                }
                for h in result.deep_hits
            ],
        } if deep_pattern is not None else None,
        "chain_view": result.chain_view,
    }


def command(
    filter_term: str = typer.Argument(
        None,
        metavar="[FILTER]",
        help="Optional substring (case-insensitive) matched against tags / summary / label / project / branch / session_id / chain_id / last_exchange.",
    ),
    active: bool = typer.Option(
        False, "--active", help="Show only sessions with status=active."
    ),
    orphans: bool = typer.Option(
        False,
        "--orphans",
        help="Show filesystem-only active dirs not in manifest (legacy / un-checked-in sessions).",
    ),
    chain: bool = typer.Option(
        False, "--chain", help="Group entries by chain_id with chain ordering."
    ),
    since: str = typer.Option(
        None,
        "--since",
        metavar="WHEN",
        help="Filter by date: today | week | month | YYYY-MM-DD.",
    ),
    deep: str = typer.Option(
        None,
        "--deep",
        metavar="PATTERN",
        help="Grep through archived artifact text for PATTERN.",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit a machine-readable JSON result on stdout."
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Print debug info to stderr."
    ),
) -> None:
    """List session-kit sessions from the manifest.

    Without flags: archived sessions, newest first.
      --active        Only sessions still in flight.
      --orphans       Active directories on disk that never registered.
      --chain         Group by chain_id; show fork relationships.
      --since <when>  Date filter (today, week, month, YYYY-MM-DD).
      --deep <text>   Grep through archived artifact bodies.
      <filter>        Positional substring filter; combines with above flags.

    Exit codes:
      0  success
      3  usage error (bad --since value)
    """
    try:
        result = run_index(
            filter_term=filter_term,
            active_only=active,
            orphans_only=orphans,
            chain=chain,
            since=since,
            deep=deep,
            json_out=json_out,
        )
    except ValueError as exc:
        print(f"usage: {exc}", file=sys.stderr)
        raise typer.Exit(code=EXIT_USAGE)

    if debug:
        print(
            f"[debug] active={len(result.active)} archived={len(result.archived)} "
            f"orphans={len(result.orphans)} deep_hits={len(result.deep_hits)} "
            f"chain={result.chain_view}",
            file=sys.stderr,
        )

    if json_out:
        json.dump(_to_jsonable(result, deep), sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        sys.stdout.write(
            _render(
                result,
                now=datetime.now(timezone.utc),
                deep_pattern=deep,
                orphans_only=orphans,
            )
        )

    raise typer.Exit(code=EXIT_OK)
