#!/usr/bin/env bash
set -euo pipefail

UV_INSTALL_DIR="${UV_INSTALL_DIR:-$HOME/.local}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.cache/uv}"
UV_INSTALL_LOCK_FILE="${UV_INSTALL_LOCK_FILE:-$UV_INSTALL_DIR/install.lock}"
UV_INSTALL_URL="${UV_INSTALL_URL:-https://astral.sh/uv/install.sh}"

mkdir -p "$UV_INSTALL_DIR" "$UV_CACHE_DIR" "$(dirname "$UV_INSTALL_LOCK_FILE")"
export UV_CACHE_DIR

uv_is_ready() {
  [[ -x "$UV_INSTALL_DIR/bin/uv" ]] && "$UV_INSTALL_DIR/bin/uv" --version >/dev/null 2>&1
}

install_uv() {
  if uv_is_ready; then
    echo "Using cached uv from $UV_INSTALL_DIR"
    return
  fi

  rm -f "$UV_INSTALL_DIR/bin/uv" "$UV_INSTALL_DIR/bin/uvx"
  curl -LsSf "$UV_INSTALL_URL" | env -u UV_INSTALL_DIR UV_UNMANAGED_INSTALL="$UV_INSTALL_DIR/bin" sh
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$UV_INSTALL_LOCK_FILE"
  flock 9
  install_uv
else
  install_uv
fi

if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "$UV_INSTALL_DIR/bin" >> "$GITHUB_PATH"
fi

"$UV_INSTALL_DIR/bin/uv" --version
