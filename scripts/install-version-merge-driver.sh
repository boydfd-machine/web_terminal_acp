#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
driver_script="$repo_root/scripts/merge-version-conflict.py"
driver_command="python3 scripts/merge-version-conflict.py %O %A %B %P"

if [[ ! -f "$driver_script" ]]; then
  echo "Missing merge driver script: $driver_script" >&2
  exit 1
fi

chmod +x "$driver_script"

git config --local merge.web-terminal-version.name \
  "Web Terminal ACP version-file merge driver"
git config --local merge.web-terminal-version.driver \
  "$driver_command"

echo "Installed web-terminal-version merge driver for $repo_root"
