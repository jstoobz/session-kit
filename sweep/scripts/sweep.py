#!/usr/bin/env python3
"""
Interactive session cleanup for Claude Code.

Scans session indexes, presents cleanup candidates, and deletes
selected sessions (both index entries and .jsonl files).

Usage:
    python3 sweep.py [--project PATH] [--dry-run] [--max-age DAYS] [--min-messages N]
"""

import json
import os
import sys
import glob
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude" / "projects"

GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def find_project_dirs():
    """Find all project directories with session indexes."""
    results = []
    for idx_file in CLAUDE_DIR.glob("*/sessions-index.json"):
        project_dir = idx_file.parent
        try:
            data = json.loads(idx_file.read_text())
            count = len(data.get("entries", []))
            results.append((project_dir, count))
        except:
            pass
    return sorted(results, key=lambda x: x[1], reverse=True)


def load_index(project_dir):
    """Load session index for a project."""
    idx_file = project_dir / "sessions-index.json"
    return json.loads(idx_file.read_text())


def save_index(project_dir, data):
    """Save session index."""
    idx_file = project_dir / "sessions-index.json"
    idx_file.write_text(json.dumps(data, indent=2))


def parse_date(date_str):
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        return None


def categorize_sessions(entries, max_age_days=14, min_messages=3):
    """Categorize sessions into cleanup candidates."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)

    categories = {
        "old_unnamed": [],  # Old + no custom title
        "old_tiny": [],  # Old + <=2 messages
        "tiny_unnamed": [],  # Any age, <=2 messages, no title
        "old_named": [],  # Old but has a name (show but don't auto-select)
        "keep": [],  # Recent or significant
    }

    for entry in entries:
        modified = parse_date(entry.get("modified"))
        has_title = bool(entry.get("customTitle"))
        msg_count = entry.get("messageCount", 0)
        is_old = modified and modified < cutoff
        is_tiny = msg_count <= min_messages

        if is_old and not has_title:
            categories["old_unnamed"].append(entry)
        elif is_old and is_tiny:
            categories["old_tiny"].append(entry)
        elif is_tiny and not has_title:
            categories["tiny_unnamed"].append(entry)
        elif is_old and has_title:
            categories["old_named"].append(entry)
        else:
            categories["keep"].append(entry)

    return categories


def display_entry(entry, selected=False):
    """Format a session entry for display."""
    sid = entry["sessionId"][:8]
    title = entry.get("customTitle", "")
    summary = (entry.get("summary") or "no summary")[:55]
    msgs = entry.get("messageCount", 0)
    modified = (entry.get("modified") or "?")[:10]
    branch = entry.get("gitBranch", "")

    marker = f"{GREEN}[x]{RESET}" if selected else f"{DIM}[ ]{RESET}"
    name_display = f"{BOLD}{title}{RESET}" if title else f"{DIM}{summary}{RESET}"

    return f"  {marker} {sid} {name_display}  {DIM}({msgs} msgs, {modified}, {branch}){RESET}"


def interactive_select(entries, category_name, auto_select=True):
    """Present entries and let user toggle selection."""
    if not entries:
        return []

    selected = set(range(len(entries))) if auto_select else set()

    print(f"\n{BOLD}{category_name}{RESET} ({len(entries)} sessions)")
    print(
        f"  {DIM}Enter numbers to toggle, 'a' for all, 'n' for none, 'done' to proceed{RESET}"
    )
    print()

    for i, entry in enumerate(entries):
        print(f"  {i + 1:3d}. {display_entry(entry, i in selected)}")

    while True:
        try:
            choice = input(f"\n  {CYAN}Toggle>{RESET} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return []

        if choice in ("done", "d", ""):
            break
        elif choice in ("all", "a"):
            selected = set(range(len(entries)))
        elif choice in ("none", "n"):
            selected = set()
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(entries):
                selected.symmetric_difference_update({idx})
            else:
                print(f"  {RED}Invalid number{RESET}")
                continue
        else:
            continue

        # Redisplay
        print()
        for i, entry in enumerate(entries):
            print(f"  {i + 1:3d}. {display_entry(entry, i in selected)}")

    return [entries[i] for i in sorted(selected)]


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Claude Code session cleanup"
    )
    parser.add_argument(
        "--project", help="Project directory path (auto-detected if not set)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without deleting"
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=14,
        help="Days before a session is 'old' (default: 14)",
    )
    parser.add_argument(
        "--min-messages",
        type=int,
        default=2,
        help="Minimum messages to be 'significant' (default: 2)",
    )
    args = parser.parse_args()

    # Find project
    if args.project:
        project_dir = Path(args.project)
    else:
        projects = find_project_dirs()
        if not projects:
            print(f"{RED}No projects with sessions found{RESET}")
            sys.exit(1)

        print(f"\n{BOLD}Projects with sessions:{RESET}\n")
        for i, (proj, count) in enumerate(projects):
            # Claude Code project dirs are named like -Users-username-path-to-project
            # Convert back to a readable path by replacing the home prefix and separators
            home_prefix = f"-Users-{Path.home().name}-"
            name = proj.name
            if name.startswith(home_prefix.lstrip("-")):
                name = "~/" + name[len(home_prefix.lstrip("-")):]
            elif f"-Users-" in name:
                # Handle any username
                parts = name.split("-Users-", 1)
                if len(parts) == 2:
                    rest = parts[1]
                    user_and_path = rest.split("-", 1)
                    if len(user_and_path) == 2:
                        name = "~/" + user_and_path[1]
            name = name.replace("-", "/")
            print(f"  {i + 1}. {name} ({count} sessions)")

        try:
            choice = input(f"\n  {CYAN}Select project>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(projects):
            print(f"{RED}Invalid selection{RESET}")
            sys.exit(1)

        project_dir = projects[int(choice) - 1][0]

    # Load and categorize
    data = load_index(project_dir)
    entries = data.get("entries", [])
    cats = categorize_sessions(entries, args.max_age, args.min_messages)

    print(f"\n{BOLD}Session Analysis:{RESET}")
    print(f"  Total sessions: {len(entries)}")
    print(
        f"  Old + unnamed:  {len(cats['old_unnamed'])} {DIM}(auto-selected for cleanup){RESET}"
    )
    print(
        f"  Old + tiny:     {len(cats['old_tiny'])} {DIM}(auto-selected for cleanup){RESET}"
    )
    print(
        f"  Tiny + unnamed: {len(cats['tiny_unnamed'])} {DIM}(auto-selected for cleanup){RESET}"
    )
    print(f"  Old + named:    {len(cats['old_named'])} {DIM}(review manually){RESET}")
    print(f"  Keep:           {len(cats['keep'])} {DIM}(recent/significant){RESET}")

    # Interactive selection per category
    to_delete = []
    to_delete += interactive_select(
        cats["old_unnamed"], "Old & Unnamed (safe to remove)", auto_select=True
    )
    to_delete += interactive_select(
        cats["old_tiny"], "Old & Tiny (<=2 messages)", auto_select=True
    )
    to_delete += interactive_select(
        cats["tiny_unnamed"], "Tiny & Unnamed (any age)", auto_select=True
    )
    to_delete += interactive_select(
        cats["old_named"], "Old but Named (review carefully)", auto_select=False
    )

    if not to_delete:
        print(f"\n{GREEN}Nothing selected for cleanup.{RESET}")
        sys.exit(0)

    # Confirm
    print(f"\n{BOLD}Will delete {len(to_delete)} sessions:{RESET}")
    for entry in to_delete:
        title = entry.get("customTitle") or entry.get("summary", "unnamed")[:50]
        print(f"  {RED}x{RESET} {entry['sessionId'][:8]} {title}")

    if args.dry_run:
        print(f"\n{YELLOW}DRY RUN — no files deleted{RESET}")
        sys.exit(0)

    try:
        confirm = (
            input(f"\n  {RED}Delete these {len(to_delete)} sessions? (yes/no)>{RESET} ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print(f"\n{YELLOW}Cancelled{RESET}")
        sys.exit(0)

    if confirm != "yes":
        print(f"{YELLOW}Cancelled{RESET}")
        sys.exit(0)

    # Delete
    delete_ids = {e["sessionId"] for e in to_delete}
    deleted_files = 0

    for entry in to_delete:
        # Delete .jsonl file
        jsonl = project_dir / f"{entry['sessionId']}.jsonl"
        if jsonl.exists():
            jsonl.unlink()
            deleted_files += 1

        # Delete session directory if it exists
        session_dir = project_dir / entry["sessionId"]
        if session_dir.is_dir():
            import shutil

            shutil.rmtree(session_dir)

    # Update index
    data["entries"] = [e for e in data["entries"] if e["sessionId"] not in delete_ids]
    save_index(project_dir, data)

    remaining = len(data["entries"])
    print(f"\n{GREEN}Deleted {len(to_delete)} sessions ({deleted_files} files).{RESET}")
    print(f"{GREEN}Remaining: {remaining} sessions.{RESET}")


if __name__ == "__main__":
    main()
