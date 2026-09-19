#!/usr/bin/env bash
# Wire shared devkit agents / KB skill into this project. Windows-adapted from devkit's
# template (this machine is win32, non-admin): file links are NTFS hardlinks, dir links
# are junctions — both live-sync with ../devkit on this machine. Idempotent; safe to re-run.
# On a *nix clone, replace the PowerShell calls with ln -s (links won't travel in git either way).
set -euo pipefail
DEVKIT="../devkit"
[ -d "$DEVKIT/agents" ] || { echo "devkit not found at $DEVKIT — fix DEVKIT or run from project root"; exit 1; }
mkdir -p .claude/agents .claude/skills

link_file() { # hardlink a single devkit file into .claude (args: devkit-rel project-rel)
  powershell -NoProfile -Command "
    \$p='$2'; if (Test-Path \$p) { Remove-Item \$p -Force }
    New-Item -ItemType HardLink -Path \$p -Target '$1' | Out-Null"
  echo "agent/file: $(basename "$2")"
}
link_dir() { # junction a devkit dir into .claude (args: devkit-rel project-rel)
  powershell -NoProfile -Command "
    \$p='$2'; if (Test-Path \$p) { Remove-Item \$p -Force -Recurse }
    New-Item -ItemType Junction -Path \$p -Target '$1' | Out-Null"
  echo "skill/dir:  $(basename "$2")"
}

for a in code-reviewer code-explorer; do
  [ -f "$DEVKIT/agents/$a.md" ] || { echo "skip: no agent '$a' in devkit"; continue; }
  link_file "$DEVKIT/agents/$a.md" ".claude/agents/$a.md"
done

[ -d "$DEVKIT/skills/knowledge-management" ] && \
  link_dir "$DEVKIT/skills/knowledge-management" ".claude/skills/knowledge-management"

echo "done."
