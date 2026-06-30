from app.agent_plugins import get_agent_plugin_registry
from app.client_agent.shell_hook.common_hooks import _common_hook_script
from app.client_agent.shell_hook.launchers import (
    _agent_home_prepare_for_command_script,
    _agent_permission_wrapper_script,
    _claude_trust_marker_script,
    _codex_trust_marker_script,
    _cursor_trust_marker_script,
    _shell_words,
)


def _agent_environment_script() -> str:
    codex_plugin = get_agent_plugin_registry().by_agent_id("codex")
    claude_plugin = get_agent_plugin_registry().by_agent_id("claude")
    codex_tree_items = ("skills", "skills.disabled", "plugins", "plugins.disabled")
    claude_tree_items = ("skills", "skills.disabled", "plugins", "plugins.disabled")
    codex_root_items = tuple(
        item
        for item in dict.fromkeys(("auth.json", *codex_plugin.storage.config_item_names))
        if item not in codex_tree_items
    )
    claude_root_items = tuple(
        item for item in claude_plugin.storage.config_item_names if item not in claude_tree_items
    )
    script = r'''__wt_link_tree() {
  [ -d "$1" ] || return 0
  mkdir -p "$2" 2>/dev/null || return 0
  find "$1" -mindepth 1 -maxdepth 1 2>/dev/null | while IFS= read -r c; do
    b="${c##*/}"
    [ ! -e "$2/$b" ] && [ ! -L "$2/$b" ] || continue
    [ -d "$c" ] && ln -s "$c" "$2/$b" 2>/dev/null && continue
    [ -f "$c" ] && cp -p "$c" "$2/$b" 2>/dev/null || true
  done
}
__web_terminal_prepare_codex_home() {
  [ -n "$WEB_TERMINAL_CODEX_HOME" ] || return 0
  __web_terminal_source_codex_home="${WEB_TERMINAL_ORIGINAL_CODEX_HOME:-${CODEX_HOME:-$HOME/.codex}}"
  case "$__web_terminal_source_codex_home" in
    "~/"*) __web_terminal_source_codex_home="$HOME/${__web_terminal_source_codex_home#"~/"}" ;;
  esac
  case "$WEB_TERMINAL_CODEX_HOME" in
    "~/"*) WEB_TERMINAL_CODEX_HOME="$HOME/${WEB_TERMINAL_CODEX_HOME#"~/"}" ;;
  esac
  if [ -d "$WEB_TERMINAL_CODEX_HOME" ]; then
    export CODEX_HOME="$WEB_TERMINAL_CODEX_HOME"
    [ ! -r "$WEB_TERMINAL_CODEX_HOME/model-env.sh" ] || . "$WEB_TERMINAL_CODEX_HOME/model-env.sh"
    __web_terminal_mark_codex_folder_trusted
    return 0
  fi
  mkdir -p "$WEB_TERMINAL_CODEX_HOME/sessions" "$WEB_TERMINAL_CODEX_HOME/log" "$WEB_TERMINAL_CODEX_HOME/shell_snapshots" 2>/dev/null || return 0
  mkdir -p "$HOME/.web-terminal-acp/shared-cache/codex/tmp" 2>/dev/null || true
  if [ ! -e "$WEB_TERMINAL_CODEX_HOME/.tmp" ] && [ ! -L "$WEB_TERMINAL_CODEX_HOME/.tmp" ]; then
    ln -s "$HOME/.web-terminal-acp/shared-cache/codex/tmp" "$WEB_TERMINAL_CODEX_HOME/.tmp" 2>/dev/null || true
  fi
  for __web_terminal_codex_item in auth.json config.toml hooks hooks.json hooks.disabled.json AGENTS.md plugin_marketplaces.json; do
    [ -e "$__web_terminal_source_codex_home/$__web_terminal_codex_item" ] || continue
    [ -e "$WEB_TERMINAL_CODEX_HOME/$__web_terminal_codex_item" ] && continue
    ln -s "$__web_terminal_source_codex_home/$__web_terminal_codex_item" "$WEB_TERMINAL_CODEX_HOME/$__web_terminal_codex_item" 2>/dev/null || true
  done
  for __web_terminal_codex_tree_item in skills skills.disabled plugins plugins.disabled; do
    __wt_link_tree "$__web_terminal_source_codex_home/$__web_terminal_codex_tree_item" "$WEB_TERMINAL_CODEX_HOME/$__web_terminal_codex_tree_item"
  done
  for __web_terminal_codex_history_item in history.json history.jsonl; do
    [ -e "$__web_terminal_source_codex_home/$__web_terminal_codex_history_item" ] || continue
    [ -e "$WEB_TERMINAL_CODEX_HOME/$__web_terminal_codex_history_item" ] && continue
    ln -s "$__web_terminal_source_codex_home/$__web_terminal_codex_history_item" "$WEB_TERMINAL_CODEX_HOME/$__web_terminal_codex_history_item" 2>/dev/null || true
  done
  export CODEX_HOME="$WEB_TERMINAL_CODEX_HOME"
  [ ! -r "$WEB_TERMINAL_CODEX_HOME/model-env.sh" ] || . "$WEB_TERMINAL_CODEX_HOME/model-env.sh"
  __web_terminal_mark_codex_folder_trusted
}
__web_terminal_export_env_line() {
  case "$1" in
    OPENAI_*=*|ANTHROPIC_*=*|CLAUDE_CODE_*=*|HTTP_PROXY=*|HTTPS_PROXY=*|NO_PROXY=*|http_proxy=*|https_proxy=*|no_proxy=*)
      export "$1"
      ;;
  esac
}
__web_terminal_load_claude_settings_env() {
  [ -r "$1" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  __web_terminal_settings_env=$(python3 - "$1" <<'WEB_TERMINAL_CLAUDE_SETTINGS_PY'
import json
import shlex
import sys

try:
    env = json.load(open(sys.argv[1], encoding="utf-8")).get("env", {})
except Exception:
    env = {}

if isinstance(env, dict):
    for key, value in env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if key.startswith(("ANTHROPIC_", "CLAUDE_CODE_")) or key in {
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
        }:
            print(f"{key}={shlex.quote(value)}")
WEB_TERMINAL_CLAUDE_SETTINGS_PY
  ) || return 0
  while IFS= read -r __web_terminal_env_line; do
    [ -n "$__web_terminal_env_line" ] || continue
    eval "__web_terminal_export_env_line $__web_terminal_env_line"
  done <<WEB_TERMINAL_CLAUDE_SETTINGS_ENV
$__web_terminal_settings_env
WEB_TERMINAL_CLAUDE_SETTINGS_ENV
  unset __web_terminal_settings_env __web_terminal_env_line
}
__web_terminal_prepare_claude_code_home() {
  [ -n "$WEB_TERMINAL_CLAUDE_CODE_HOME" ] || return 0
  __web_terminal_source_claude_home="${WEB_TERMINAL_ORIGINAL_CLAUDE_CODE_HOME:-$HOME/.claude}"
  case "$__web_terminal_source_claude_home" in
    "~/"*) __web_terminal_source_claude_home="$HOME/${__web_terminal_source_claude_home#"~/"}" ;;
  esac
  case "$WEB_TERMINAL_CLAUDE_CODE_HOME" in
    "~/"*) WEB_TERMINAL_CLAUDE_CODE_HOME="$HOME/${WEB_TERMINAL_CLAUDE_CODE_HOME#"~/"}" ;;
  esac
  if [ -d "$WEB_TERMINAL_CLAUDE_CODE_HOME" ]; then
    __web_terminal_load_claude_settings_env "$__web_terminal_source_claude_home/settings.json"
    export CLAUDE_CONFIG_DIR="$WEB_TERMINAL_CLAUDE_CODE_HOME"
    [ ! -r "$WEB_TERMINAL_CLAUDE_CODE_HOME/model-env.sh" ] || . "$WEB_TERMINAL_CLAUDE_CODE_HOME/model-env.sh"
    __web_terminal_mark_claude_code_folder_trusted
    return 0
  fi
  mkdir -p "$WEB_TERMINAL_CLAUDE_CODE_HOME/projects" 2>/dev/null || true
  __web_terminal_source_claude_json="${WEB_TERMINAL_ORIGINAL_CLAUDE_JSON:-$HOME/.claude.json}"
  case "$__web_terminal_source_claude_json" in
    "~/"*) __web_terminal_source_claude_json="$HOME/${__web_terminal_source_claude_json#"~/"}" ;;
  esac
  if [ -e "$__web_terminal_source_claude_json" ] && [ ! -e "$WEB_TERMINAL_CLAUDE_CODE_HOME/.claude.json" ]; then
    ln -s "$__web_terminal_source_claude_json" "$WEB_TERMINAL_CLAUDE_CODE_HOME/.claude.json" 2>/dev/null || true
  fi
  for __web_terminal_claude_item in settings.json settings.local.json commands hooks hooks.disabled.json api-key-helper.sh; do
    [ -e "$__web_terminal_source_claude_home/$__web_terminal_claude_item" ] || continue
    [ -e "$WEB_TERMINAL_CLAUDE_CODE_HOME/$__web_terminal_claude_item" ] && continue
    ln -s "$__web_terminal_source_claude_home/$__web_terminal_claude_item" "$WEB_TERMINAL_CLAUDE_CODE_HOME/$__web_terminal_claude_item" 2>/dev/null || true
  done
  for __web_terminal_claude_tree_item in CLAUDE_TREE_ITEMS_PLACEHOLDER; do
    __wt_link_tree "$__web_terminal_source_claude_home/$__web_terminal_claude_tree_item" "$WEB_TERMINAL_CLAUDE_CODE_HOME/$__web_terminal_claude_tree_item"
  done
  for __web_terminal_claude_history_item in history.json history.jsonl file-history; do
    [ -e "$__web_terminal_source_claude_home/$__web_terminal_claude_history_item" ] || continue
    [ -e "$WEB_TERMINAL_CLAUDE_CODE_HOME/$__web_terminal_claude_history_item" ] && continue
    ln -s "$__web_terminal_source_claude_home/$__web_terminal_claude_history_item" "$WEB_TERMINAL_CLAUDE_CODE_HOME/$__web_terminal_claude_history_item" 2>/dev/null || true
  done
  __web_terminal_load_claude_settings_env "$__web_terminal_source_claude_home/settings.json"
  export CLAUDE_CONFIG_DIR="$WEB_TERMINAL_CLAUDE_CODE_HOME"
  [ ! -r "$WEB_TERMINAL_CLAUDE_CODE_HOME/model-env.sh" ] || . "$WEB_TERMINAL_CLAUDE_CODE_HOME/model-env.sh"
  __web_terminal_mark_claude_code_folder_trusted
}
__web_terminal_expand_home_path() {
  case "$1" in
    "~"*) printf '%s\n' "$HOME${1#\~}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}
__web_terminal_prepend_path_once() {
  __web_terminal_path_to_add=$(__web_terminal_expand_home_path "$1")
  [ -n "$__web_terminal_path_to_add" ] || return 0
  case ":$PATH:" in
    *":$__web_terminal_path_to_add:"*) ;;
    *) export PATH="$__web_terminal_path_to_add:$PATH" ;;
  esac
}
__web_terminal_prepare_agent_command_path() {
  for __web_terminal_bin_dir in "~/.web-terminal-acp/npm-global/bin" "~/.local/bin" "~/.npm-global/bin" "~/.npm-packages/bin" "~/.bun/bin" "~/.cargo/bin" "/opt/homebrew/bin" "/usr/local/bin"; do
    __web_terminal_prepend_path_once "$__web_terminal_bin_dir"
  done
}
__web_terminal_agent_command_available() {
  command -v "$1" >/dev/null 2>&1
}
__web_terminal_cursor_skill_home_dir() {
  [ -n "$WEB_TERMINAL_CURSOR_HOME" ] || return 1
  local managed_cursor overlay item __web_terminal_original_home
  case "$WEB_TERMINAL_CURSOR_HOME" in
    "~/"*) managed_cursor="$HOME/${WEB_TERMINAL_CURSOR_HOME#"~/"}" ;;
    *) managed_cursor="$WEB_TERMINAL_CURSOR_HOME" ;;
  esac
  overlay="$managed_cursor/skill-home"
  mkdir -p "$overlay/.cursor" "$overlay/.claude" "$overlay/.codex" "$overlay/.agents" 2>/dev/null || return 1
  ln -sfn "$managed_cursor/cli-config.json" "$overlay/.cursor/cli-config.json" 2>/dev/null || return 1; ln -sfn "$managed_cursor/agent-cli-state.json" "$overlay/.cursor/agent-cli-state.json" 2>/dev/null || return 1; mkdir -p "$managed_cursor/projects" 2>/dev/null || return 1; rm -rf "$overlay/.cursor/projects" 2>/dev/null || true; ln -sfn "$managed_cursor/projects" "$overlay/.cursor/projects" 2>/dev/null || return 1; for item in 1 managed; do [ -e "$managed_cursor/$item" ] || [ -L "$managed_cursor/$item" ] || continue; [ -e "$overlay/.cursor/$item" ] || [ -L "$overlay/.cursor/$item" ] || ln -s "$managed_cursor/$item" "$overlay/.cursor/$item" 2>/dev/null || true; done; __web_terminal_original_home="${WEB_TERMINAL_ORIGINAL_HOME:-$HOME}"; case "$__web_terminal_original_home" in "~"*) __web_terminal_original_home="$HOME${__web_terminal_original_home#\~}" ;; esac; if [ -e "$__web_terminal_original_home/.config/cursor/auth.json" ] || [ -L "$__web_terminal_original_home/.config/cursor/auth.json" ]; then mkdir -p "$overlay/.config/cursor" 2>/dev/null || true; ln -sfn "$__web_terminal_original_home/.config/cursor/auth.json" "$overlay/.config/cursor/auth.json" 2>/dev/null || true; fi
  if [ -d "$managed_cursor/skills-cursor" ]; then
    ln -sfn "$managed_cursor/skills-cursor" "$overlay/.cursor/skills-cursor" 2>/dev/null || return 1
  else
    mkdir -p "$overlay/.cursor/skills-cursor" 2>/dev/null || return 1
  fi
  mkdir -p "$overlay/.claude/skills" "$overlay/.codex/skills" "$overlay/.cursor/skills" "$overlay/.agents/skills" 2>/dev/null || return 1
  printf '%s\n' "$overlay"
}
__web_terminal_prepare_cursor_skill_home() {
  local overlay; overlay="$(__web_terminal_cursor_skill_home_dir)" || return 1
  export WEB_TERMINAL_CURSOR_SKILL_HOME="$overlay"
}
__web_terminal_run_cursor_agent_command() {
  __web_terminal_command_name="$1"
  shift
  __web_terminal_prepare_cursor_skill_home || {
    command "$__web_terminal_command_name" "$@"
    return $?
  }
  HOME="$WEB_TERMINAL_CURSOR_SKILL_HOME" \
    WEB_TERMINAL_ORIGINAL_HOME="${WEB_TERMINAL_ORIGINAL_HOME:-$HOME}" \
    command "$__web_terminal_command_name" "$@"
}
__web_terminal_prepare_cursor_home() {
  [ -n "$WEB_TERMINAL_CURSOR_HOME" ] || return 0
  local managed_cursor source_cursor item base
  case "$WEB_TERMINAL_CURSOR_HOME" in
    "~/"*) managed_cursor="$HOME/${WEB_TERMINAL_CURSOR_HOME#"~/"}" ;;
    *) managed_cursor="$WEB_TERMINAL_CURSOR_HOME" ;;
  esac
  case "${WEB_TERMINAL_ORIGINAL_CURSOR_DIR:-$HOME/.cursor}" in
    "~/"*) source_cursor="$HOME/${WEB_TERMINAL_ORIGINAL_CURSOR_DIR#"~/"}" ;;
    *) source_cursor="${WEB_TERMINAL_ORIGINAL_CURSOR_DIR:-$HOME/.cursor}" ;;
  esac
  if [ -d "$managed_cursor" ]; then
    if [ -L "$managed_cursor/chats" ]; then
      rm -f "$managed_cursor/chats" 2>/dev/null || true
      mkdir -p "$managed_cursor/chats" 2>/dev/null || true
    fi
    mkdir -p "$managed_cursor/projects" 2>/dev/null || true; for item in 1 managed; do [ -e "$source_cursor/$item" ] || [ -L "$source_cursor/$item" ] || continue; [ -e "$managed_cursor/$item" ] || [ -L "$managed_cursor/$item" ] || ln -s "$source_cursor/$item" "$managed_cursor/$item" 2>/dev/null || true; done
    export CURSOR_AGENT_HOME="$managed_cursor"
    export CURSOR_CONFIG_DIR="$managed_cursor"
    export CURSOR_DATA_DIR="$managed_cursor"
    __web_terminal_configure_cursor_statusline "$managed_cursor"
    __web_terminal_prepare_cursor_skill_home
    __web_terminal_mark_cursor_folder_trusted
    return 0
  fi
  mkdir -p "$managed_cursor/chats" "$managed_cursor/projects" 2>/dev/null || true
  if [ -L "$managed_cursor/chats" ]; then
    rm -f "$managed_cursor/chats" 2>/dev/null || true
    mkdir -p "$managed_cursor/chats" 2>/dev/null || true
  fi
  find "$source_cursor" -mindepth 1 -maxdepth 1 2>/dev/null | while IFS= read -r item; do
    base="${item##*/}"
    case "$base" in
      chats|projects) continue ;;
      skills-cursor|skills-cursor.disabled)
        continue
        ;;
      plugins|plugins.disabled)
        __wt_link_tree "$item" "$managed_cursor/$base"
        continue
        ;;
    esac
    [ -e "$managed_cursor/$base" ] && continue
    ln -sf "$item" "$managed_cursor/$base" 2>/dev/null || true
  done
  export CURSOR_AGENT_HOME="$managed_cursor"
  export CURSOR_CONFIG_DIR="$managed_cursor"
  export CURSOR_DATA_DIR="$managed_cursor"
  __web_terminal_configure_cursor_statusline "$managed_cursor"
  mkdir -p "$managed_cursor/skills-cursor" "$managed_cursor/skills-cursor.disabled" 2>/dev/null || true
  __web_terminal_prepare_cursor_skill_home
  __web_terminal_mark_cursor_folder_trusted
}
__web_terminal_configure_cursor_statusline() {
  local managed_cursor="$1"
  [ -n "$managed_cursor" ] || return 0
  local bin_dir="$managed_cursor/bin"
  local script="$bin_dir/cursor-statusline-writer.sh"
  local config="$managed_cursor/cli-config.json"
  mkdir -p "$bin_dir" 2>/dev/null || true
  cat > "$script" << 'EOF'
#!/usr/bin/env bash
payload=$(cat)
[ -n "${CURSOR_DATA_DIR:-}" ] || exit 0
out="${CURSOR_DATA_DIR}/statusline-usage.json"
tmp="${out}.tmp.$$"
printf '%s\n' "$payload" > "$tmp"
mv "$tmp" "$out"
EOF
  chmod +x "$script" 2>/dev/null || true
  if [ -L "$config" ]; then
    cp -L "$config" "${config}.tmp" 2>/dev/null && mv "${config}.tmp" "$config" 2>/dev/null || true
  fi
  python3 - "$config" "$script" << 'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
script_path = sys.argv[2]
config = {}
if config_path.is_file():
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        parsed = {}
    if isinstance(parsed, dict):
        config = parsed
config["statusLine"] = {
    "type": "command",
    "command": script_path,
    "updateIntervalMs": 500,
    "timeoutMs": 1000,
}
config_path.parent.mkdir(parents=True, exist_ok=True)
config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
}
__web_terminal_prepare_antigravity_home() {
  [ -n "$WEB_TERMINAL_ANTIGRAVITY_HOME" ] || return 0
  local managed_antigravity source_antigravity item base command_home original_home workspace_root cache_home
  case "$WEB_TERMINAL_ANTIGRAVITY_HOME" in
    "~/"*) managed_antigravity="$HOME/${WEB_TERMINAL_ANTIGRAVITY_HOME#"~/"}" ;;
    *) managed_antigravity="$WEB_TERMINAL_ANTIGRAVITY_HOME" ;;
  esac
  case "${WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME:-$HOME/.gemini/antigravity-cli}" in
    "~/"*) source_antigravity="$HOME/${WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME#"~/"}" ;;
    *) source_antigravity="${WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME:-$HOME/.gemini/antigravity-cli}" ;;
  esac
  if [ ! -d "$managed_antigravity" ]; then
    mkdir -p "$managed_antigravity" 2>/dev/null || true
    find "$source_antigravity" -mindepth 1 -maxdepth 1 2>/dev/null | while IFS= read -r item; do
      base="${item##*/}"
      case "$base" in
        brain|cache|log|scratch) continue ;;
        plugins|plugins.disabled|skills|skills.disabled)
          __wt_link_tree "$item" "$managed_antigravity/$base"
          continue
          ;;
      esac
      [ -e "$managed_antigravity/$base" ] && continue
      ln -sf "$item" "$managed_antigravity/$base" 2>/dev/null || true
    done
    if [ -f "$source_antigravity/cache/onboarding.json" ] && [ ! -f "$managed_antigravity/cache/onboarding.json" ]; then
      mkdir -p "$managed_antigravity/cache" 2>/dev/null || true
      cp "$source_antigravity/cache/onboarding.json" "$managed_antigravity/cache/onboarding.json" 2>/dev/null || true
    fi
  fi
  command_home="${WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME:-}"
  if [ -n "$command_home" ]; then
    case "$command_home" in
      "~/"*) command_home="$HOME/${command_home#"~/"}" ;;
    esac
    mkdir -p "$command_home/.gemini" 2>/dev/null || true
    if [ ! -e "$command_home/.gemini/antigravity-cli" ] && [ ! -L "$command_home/.gemini/antigravity-cli" ]; then
      ln -s "$managed_antigravity" "$command_home/.gemini/antigravity-cli" 2>/dev/null || true
    fi
  fi
  original_home="${WEB_TERMINAL_ORIGINAL_HOME:-$HOME}"
  case "$original_home" in
    "~"*) original_home="$HOME${original_home#\~}" ;;
  esac
  cache_home="${WEB_TERMINAL_ANTIGRAVITY_CACHE_HOME:-$original_home/.web-terminal-acp/shared-cache/antigravity}"
  case "$cache_home" in
    "~"*) cache_home="$original_home${cache_home#\~}" ;;
  esac
  mkdir -p "$cache_home" 2>/dev/null || true
  workspace_root="${AGY_PROXY_WORKSPACE_LINK_ROOT:-$original_home/agy-workspaces}"
  case "$workspace_root" in
    "~"*) workspace_root="$original_home${workspace_root#\~}" ;;
  esac
  export WEB_TERMINAL_ANTIGRAVITY_HOME="$managed_antigravity"
  export WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME="${command_home:-$HOME}"
  export WEB_TERMINAL_ANTIGRAVITY_CACHE_HOME="$cache_home"
  export WEB_TERMINAL_ANTIGRAVITY_PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$cache_home/ms-playwright-go}"
  export AGY_PROXY_WORKSPACE_LINK_ROOT="$workspace_root"
}
__web_terminal_missing_claude_env() {
  { [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; } || return 0
  [ -n "${ANTHROPIC_BASE_URL:-}" ] || [ -n "${CLAUDE_CODE_API_BASE_URL:-}" ] || return 0
  return 1
}
__web_terminal_load_zshrc_env() {
  [ -r "$HOME/.zshrc" ] || return 0
  command -v zsh >/dev/null 2>&1 || return 0
  __web_terminal_zshrc_env=$(
    env -i HOME="$HOME" USER="${USER:-}" LOGNAME="${LOGNAME:-${USER:-}}" PATH="$PATH" SHELL="${SHELL:-/bin/zsh}" \
      zsh -ic 'env' 2>/dev/null
  ) || return 0
  while IFS= read -r __web_terminal_env_line; do
    case "$__web_terminal_env_line" in
      OPENAI_*=*|ANTHROPIC_*=*|CLAUDE_CODE_*=*|HTTP_PROXY=*|HTTPS_PROXY=*|NO_PROXY=*|http_proxy=*|https_proxy=*|no_proxy=*)
        __web_terminal_export_env_line "$__web_terminal_env_line"
        ;;
    esac
  done <<WEB_TERMINAL_ZSHRC_ENV
$__web_terminal_zshrc_env
WEB_TERMINAL_ZSHRC_ENV
  unset __web_terminal_zshrc_env __web_terminal_env_line
}
__web_terminal_load_user_shell_env() {
  __web_terminal_user_shell="${SHELL:-}"
  [ -n "$__web_terminal_user_shell" ] || __web_terminal_user_shell="$(command -v zsh 2>/dev/null || command -v bash 2>/dev/null || true)"
  [ -n "$__web_terminal_user_shell" ] || return 0
  [ -x "$__web_terminal_user_shell" ] || return 0
  case "${__web_terminal_user_shell##*/}" in
    zsh|bash|sh) ;;
    *) return 0 ;;
  esac
  __web_terminal_user_env=$(
    env -i HOME="$HOME" USER="${USER:-}" LOGNAME="${LOGNAME:-${USER:-}}" PATH="$PATH" SHELL="$__web_terminal_user_shell" \
      "$__web_terminal_user_shell" -ic 'env' 2>/dev/null
  ) || return 0
  while IFS= read -r __web_terminal_env_line; do
    case "$__web_terminal_env_line" in
      PATH=*)
        export "$__web_terminal_env_line"
        ;;
      OPENAI_*=*|ANTHROPIC_*=*|CLAUDE_CODE_*=*|HTTP_PROXY=*|HTTPS_PROXY=*|NO_PROXY=*|http_proxy=*|https_proxy=*|no_proxy=*)
        __web_terminal_export_env_line "$__web_terminal_env_line"
        ;;
    esac
  done <<WEB_TERMINAL_USER_SHELL_ENV
$__web_terminal_user_env
WEB_TERMINAL_USER_SHELL_ENV
  unset __web_terminal_user_shell __web_terminal_user_env __web_terminal_env_line
}
__web_terminal_agent_arg_present() {
  __web_terminal_expected="$1"
  shift
  for __web_terminal_arg in "$@"; do
    [ "$__web_terminal_arg" = "$__web_terminal_expected" ] && return 0
  done
  return 1
}
__web_terminal_run_agent_command() {
  __web_terminal_command_name="$1"
  shift
  __wt_prepare_agent_home "$__web_terminal_command_name"
  case "$__web_terminal_command_name" in
    claude)
      __web_terminal_run_claude_code_command "$@"
      ;;
    agy|agy-p)
      __web_terminal_prepare_antigravity_home
      HOME="$WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME" XDG_CACHE_HOME="$WEB_TERMINAL_ANTIGRAVITY_CACHE_HOME" PLAYWRIGHT_BROWSERS_PATH="$WEB_TERMINAL_ANTIGRAVITY_PLAYWRIGHT_BROWSERS_PATH" AGY_PROXY_WORKSPACE_LINK_ROOT="$AGY_PROXY_WORKSPACE_LINK_ROOT" command "$__web_terminal_command_name" "$@"
      ;;
    agent|cursor|cursor-agent)
      __web_terminal_run_cursor_agent_command "$__web_terminal_command_name" "$@"
      ;;
    *)
      command "$__web_terminal_command_name" "$@"
      ;;
  esac
}
__web_terminal_run_claude_code_command() {
  if [ -z "${WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT:-}" ]; then
    command claude "$@"
    return $?
  fi
  CLAUDE_CODE_ENABLE_TELEMETRY=1 \
  OTEL_METRICS_EXPORTER=otlp \
  OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/json \
  OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="$WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT" \
  OTEL_METRIC_EXPORT_INTERVAL="${OTEL_METRIC_EXPORT_INTERVAL:-5000}" \
  OTEL_RESOURCE_ATTRIBUTES="${OTEL_RESOURCE_ATTRIBUTES:+$OTEL_RESOURCE_ATTRIBUTES,}web_terminal.client_id=$WEB_TERMINAL_CLIENT_ID,web_terminal.window_id=$WEB_TERMINAL_WINDOW_ID" \
    command claude "$@"
}
__web_terminal_run_agent_command_with_permission() {
  __web_terminal_command_name="$1"
  __web_terminal_permission_flag="$2"
  shift 2
  if [ -n "$__web_terminal_permission_flag" ] && ! __web_terminal_agent_arg_present "$__web_terminal_permission_flag" "$@"; then
    set -- "$__web_terminal_permission_flag" "$@"
  fi
  __web_terminal_run_agent_command "$__web_terminal_command_name" "$@"
}
''' + _agent_home_prepare_for_command_script() + "\n" + _agent_permission_wrapper_script() + "\n" + _codex_trust_marker_script() + _claude_trust_marker_script() + _cursor_trust_marker_script() + r'''
__web_terminal_prepare_direct_agent_launch() {
  __web_terminal_prepare_agent_command_path
  if [ -n "$1" ] && ! __web_terminal_agent_command_available "$1"; then
    __web_terminal_load_user_shell_env
    __web_terminal_prepare_agent_command_path
  fi
  __wt_prepare_agent_home "$1"
  case "$1" in
    agent|cursor|cursor-agent)
      __web_terminal_prepare_cursor_skill_home && HOME="$WEB_TERMINAL_CURSOR_SKILL_HOME"
      ;;
  esac
  __web_terminal_install_agent_permission_wrappers
}
'''
    return (
        script.replace(
            "auth.json config.toml hooks hooks.json hooks.disabled.json AGENTS.md plugin_marketplaces.json",
            _shell_words(codex_root_items),
        )
        .replace(
            "skills skills.disabled plugins plugins.disabled",
            _shell_words(codex_tree_items),
            1,
        )
        .replace(
            "history.json history.jsonl",
            _shell_words(codex_plugin.storage.history_item_names),
            1,
        )
        .replace(
            "settings.json settings.local.json commands hooks hooks.disabled.json api-key-helper.sh",
            _shell_words(claude_root_items),
        )
        .replace(
            "CLAUDE_TREE_ITEMS_PLACEHOLDER",
            _shell_words(claude_tree_items),
        )
        .replace(
            "history.json history.jsonl file-history",
            _shell_words(claude_plugin.storage.history_item_names),
        )
    )
def _bash_hook_script() -> str:
    return _common_hook_script() + r'''
if __web_terminal_missing_claude_env; then
  __web_terminal_load_zshrc_env
fi
if [ -r "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
__web_terminal_install_agent_permission_wrappers
__web_terminal_last_history_id=""
__web_terminal_initial_history_line=$(HISTTIMEFORMAT= history 1 2>/dev/null || true)
__web_terminal_initial_history_line="${__web_terminal_initial_history_line#"${__web_terminal_initial_history_line%%[![:space:]]*}"}"
__web_terminal_last_history_id="${__web_terminal_initial_history_line%%[[:space:]]*}"
__web_terminal_in_hook=0
__web_terminal_start_bash_command() {
  [ "$__web_terminal_in_hook" = "1" ] && return 0
  case "$BASH_COMMAND" in
    __web_terminal_*|history\ *|trap\ *|PROMPT_COMMAND=*) return 0 ;;
  esac
  local __web_terminal_history_line __web_terminal_history_id __web_terminal_command
  __web_terminal_in_hook=1
  __web_terminal_history_line=$(HISTTIMEFORMAT= history 1 2>/dev/null)
  __web_terminal_in_hook=0
  [ -n "$__web_terminal_history_line" ] || return 0
  __web_terminal_history_line="${__web_terminal_history_line#"${__web_terminal_history_line%%[![:space:]]*}"}"
  __web_terminal_history_id="${__web_terminal_history_line%%[[:space:]]*}"
  [ -n "$__web_terminal_history_id" ] || return 0
  [ "$__web_terminal_history_id" != "$__web_terminal_last_history_id" ] || return 0
  __web_terminal_last_history_id="$__web_terminal_history_id"
  __web_terminal_command="${__web_terminal_history_line#"$__web_terminal_history_id"}"
  __web_terminal_command="${__web_terminal_command#"${__web_terminal_command%%[![:space:]]*}"}"
  [ -n "$__web_terminal_command" ] || return 0
  __web_terminal_should_capture_command "$__web_terminal_command" || return 0
  __web_terminal_sequence=$((__web_terminal_sequence + 1))
  __web_terminal_active_sequence="$__web_terminal_sequence"
  __web_terminal_active_command="$__web_terminal_command"
  __web_terminal_in_hook=1
  __web_terminal_emit_command_marker started bash "$__web_terminal_active_sequence" "" "$__web_terminal_command"
  __web_terminal_in_hook=0
}
__web_terminal_finish_bash_command() {
  local __web_terminal_status=$?
  [ -n "$__web_terminal_active_sequence" ] || return $__web_terminal_status
  __web_terminal_in_hook=1
  __web_terminal_emit_command_marker finished bash "$__web_terminal_active_sequence" "$__web_terminal_status" "$__web_terminal_active_command"
  __web_terminal_active_sequence=""
  __web_terminal_active_command=""
  __web_terminal_in_hook=0
  return $__web_terminal_status
}
trap '__web_terminal_start_bash_command' DEBUG
PROMPT_COMMAND="__web_terminal_finish_bash_command${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
'''
