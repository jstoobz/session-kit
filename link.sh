#!/usr/bin/env bash
set -euo pipefail

# Session Kit installer — symlinks skills into ~/.claude/skills/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${HOME}/.claude/skills"

mkdir -p "$SKILLS_DIR"

SKILLS=(
  checkin
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
DOCS=(session-kit.md)

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

# --- Install bin/sk dispatcher into ~/.local/bin/sk ------------------------

LOCAL_BIN="${HOME}/.local/bin"
SK_SRC="$SCRIPT_DIR/bin/sk"
SK_DEST="$LOCAL_BIN/sk"

if [ -x "$SK_SRC" ]; then
  mkdir -p "$LOCAL_BIN"
  if [ -L "$SK_DEST" ]; then
    existing="$(readlink "$SK_DEST")"
    if [ "$existing" = "$SK_SRC" ]; then
      echo "  ok    sk (already linked)"
      skipped=$((skipped + 1))
    else
      rm "$SK_DEST"
      ln -s "$SK_SRC" "$SK_DEST"
      echo "  link  sk → $SK_DEST"
      linked=$((linked + 1))
    fi
  elif [ -e "$SK_DEST" ]; then
    echo "  WARN  sk — $SK_DEST exists and is not a symlink, skipping"
    skipped=$((skipped + 1))
  else
    ln -s "$SK_SRC" "$SK_DEST"
    echo "  link  sk → $SK_DEST"
    linked=$((linked + 1))
  fi

  case ":$PATH:" in
    *":$LOCAL_BIN:"*) ;;
    *)
      echo ""
      echo "  NOTE  $LOCAL_BIN is not on your PATH."
      echo "        Add this to your shell init (e.g. ~/.zshrc):"
      echo "          export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac
fi

echo ""
echo "Done. Linked $linked item(s), $skipped unchanged."
echo ""
echo "Restart Claude Code to pick up the new skills."
