#!/bin/bash
# install.sh [--dry-run] — install skill/ as `mathproof-skill` for every agent found on this machine.
#   Targets (each only if its parent directory exists):
#     Claude Code          ~/.claude/skills
#     Codex                ~/.codex/skills
#     Antigravity (IDE)    ~/.gemini/antigravity/skills
#     Antigravity CLI agy  ~/.gemini/config/skills (global skills) and ~/.gemini/antigravity-cli/skills
#     shared Agent Skills  ~/.agents/skills
#   An older `mathproof-debug` copy (same skill, pre-rename) is moved to ~/.mathproof/backup/<stamp>/.
#   ~/.mathproof/lean is linked to this repository's lean/ project, so lean_check.py finds Mathlib.
# Re-run any time to update. scripts/uninstall.sh reverses it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
run() { if [ $DRY = 1 ]; then echo "would: $*"; else "$@"; fi; }
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HOME/.mathproof/backup/$STAMP"

TARGETS=(
  "Claude Code|$HOME/.claude/skills"
  "Codex|$HOME/.codex/skills"
  "Antigravity IDE|$HOME/.gemini/antigravity/skills"
  "Antigravity CLI (agy)|$HOME/.gemini/config/skills"
  "Antigravity CLI (agy, legacy dir)|$HOME/.gemini/antigravity-cli/skills"
  "Agent Skills (shared)|$HOME/.agents/skills"
)

for t in "${TARGETS[@]}"; do
  name="${t%%|*}"; dir="${t#*|}"
  [ -d "$(dirname "$dir")" ] || { echo "skip   $name (no $(dirname "$dir"))"; continue; }
  run mkdir -p "$dir"
  if [ -d "$dir/mathproof-debug" ]; then
    run mkdir -p "$BACKUP/$(echo "$name" | tr ' ()' '___')"
    run mv "$dir/mathproof-debug" "$BACKUP/$(echo "$name" | tr ' ()' '___')/"
    echo "backup $name: mathproof-debug → $BACKUP"
  fi
  run rm -rf "$dir/mathproof-skill"
  run cp -R "$ROOT/skill" "$dir/mathproof-skill"
  run chmod +x "$dir/mathproof-skill/scripts/lean_check.py"
  echo "skill  $name → $dir/mathproof-skill"
done

run mkdir -p "$HOME/.mathproof"
run ln -sfn "$ROOT/lean" "$HOME/.mathproof/lean"
echo "lean   ~/.mathproof/lean → $ROOT/lean"
if [ ! -d "$ROOT/lean/.lake/packages/mathlib" ]; then
  echo "NOTE: Mathlib is not downloaded yet. Run: (cd \"$ROOT/lean\" && lake exe cache get)"
fi
command -v lake >/dev/null || echo "WARNING: lake not on PATH; install elan from https://lean-lang.org/install"
echo "Restart each agent (or start a new session) so it picks up the skill."
