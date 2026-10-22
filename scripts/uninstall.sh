#!/bin/bash
# uninstall.sh — remove `mathproof-skill` from every agent and the ~/.mathproof/lean link.
# Backups of older skills under ~/.mathproof/backup are left in place; restore them by hand if wanted.
set -euo pipefail
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.gemini/antigravity/skills" \
           "$HOME/.gemini/antigravity-cli/skills" "$HOME/.agents/skills"; do
  [ -d "$dir/mathproof-skill" ] && rm -rf "$dir/mathproof-skill" && echo "removed $dir/mathproof-skill"
done
[ -L "$HOME/.mathproof/lean" ] && rm "$HOME/.mathproof/lean" && echo "removed ~/.mathproof/lean link"
echo "Backups (if any) remain in ~/.mathproof/backup."
