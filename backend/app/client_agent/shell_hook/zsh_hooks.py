from app.client_agent.shell_hook.common_hooks import _common_hook_script


def _zsh_hook_script() -> str:
    return _common_hook_script() + r'''
if [ -r "$HOME/.zshrc" ]; then
  source "$HOME/.zshrc"
fi
__web_terminal_install_agent_permission_wrappers
if whence -w preexec >/dev/null 2>&1; then
  functions -c preexec __web_terminal_user_preexec
fi
if whence -w precmd >/dev/null 2>&1; then
  functions -c precmd __web_terminal_user_precmd
fi
__web_terminal_pending_command=""
preexec() {
  __web_terminal_pending_command="$1"
  if ! __web_terminal_should_capture_command "$__web_terminal_pending_command"; then
    if whence -w __web_terminal_user_preexec >/dev/null 2>&1; then
      __web_terminal_user_preexec "$@"
    fi
    return 0
  fi
  __web_terminal_sequence=$((__web_terminal_sequence + 1))
  __web_terminal_active_sequence="$__web_terminal_sequence"
  __web_terminal_active_command="$1"
  __web_terminal_emit_command_marker started zsh "$__web_terminal_active_sequence" "" "$__web_terminal_active_command"
  if whence -w __web_terminal_user_preexec >/dev/null 2>&1; then
    __web_terminal_user_preexec "$@"
  fi
}
precmd() {
  __web_terminal_status=$?
  if [ -n "$__web_terminal_active_sequence" ]; then
    __web_terminal_emit_command_marker finished zsh "$__web_terminal_active_sequence" "$__web_terminal_status" "$__web_terminal_active_command"
    __web_terminal_active_sequence=""
    __web_terminal_active_command=""
    __web_terminal_pending_command=""
  fi
  if whence -w __web_terminal_user_precmd >/dev/null 2>&1; then
    __web_terminal_user_precmd "$@"
  fi
}
'''
