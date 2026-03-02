#!/usr/bin/env bash
set -euo pipefail

# Session Kit installer — symlinks skills into ~/.claude/skills/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${HOME}/.claude/skills"

mkdir -p "$SKILLS_DIR"

SKILLS=(
  checkpoint
  sweep
  handoff
  index
  park
  persist
  pickup
  hone
  prime
  rca
  relay
  retro
  tldr
)

linked=0
skipped=0

for skill in "${SKILLS[@]}"; do
  src="$SCRIPT_DIR/$skill"
  dest="$SKILLS_DIR/$skill"

  if [ ! -d "$src" ]; then
    echo "  skip  $skill (not found in repo)"
    skipped=$((skipped + 1))
    continue
  fi

  if [ -L "$dest" ]; then
    existing="$(readlink "$dest")"
    if [ "$existing" = "$src" ]; then
      echo "  ok    $skill (already linked)"
      skipped=$((skipped + 1))
      continue
    fi
    rm "$dest"
  elif [ -e "$dest" ]; then
    echo "  WARN  $skill — $dest exists and is not a symlink, skipping"
    skipped=$((skipped + 1))
    continue
  fi

  ln -s "$src" "$dest"
  echo "  link  $skill → $dest"
  linked=$((linked + 1))
done

# Link top-level reference docs
DOCS=(session-kit.md session-checkin.md)

for doc in "${DOCS[@]}"; do
  src="$SCRIPT_DIR/$doc"
  dest="$SKILLS_DIR/$doc"

  if [ ! -f "$src" ]; then
    continue
  fi

  if [ -L "$dest" ]; then
    existing="$(readlink "$dest")"
    if [ "$existing" = "$src" ]; then
      echo "  ok    $doc (already linked)"
      skipped=$((skipped + 1))
      continue
    fi
    rm "$dest"
  elif [ -e "$dest" ]; then
    echo "  WARN  $doc — $dest exists and is not a symlink, skipping"
    skipped=$((skipped + 1))
    continue
  fi

  ln -sf "$src" "$dest"
  echo "  link  $doc → $dest"
  linked=$((linked + 1))
done

echo ""
echo "Done. Linked $linked item(s), $skipped unchanged."
echo ""
echo "Restart Claude Code to pick up the new skills."
