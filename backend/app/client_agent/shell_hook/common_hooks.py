def _common_hook_script() -> str:
    from app.client_agent.shell_hook.bash_hooks import _agent_environment_script

    return _agent_environment_script() + r'''
__web_terminal_sequence=0
__web_terminal_active_sequence=""
__web_terminal_active_command=""
__web_terminal_emit_command_marker() {
  __web_terminal_phase="$1"
  __web_terminal_shell="$2"
  __web_terminal_sequence_value="$3"
  __web_terminal_exit_status="$4"
  shift 4
  __web_terminal_command="$*"
  [ -n "$__web_terminal_command" ] || return 0
  __web_terminal_payload=$(
    WEB_TERMINAL_CAPTURED_PHASE="$__web_terminal_phase" \
    WEB_TERMINAL_CAPTURED_COMMAND="$__web_terminal_command" \
    WEB_TERMINAL_CAPTURED_SHELL="$__web_terminal_shell" \
    WEB_TERMINAL_CAPTURED_CWD="$PWD" \
    WEB_TERMINAL_CAPTURED_SEQUENCE="$__web_terminal_sequence_value" \
    WEB_TERMINAL_CAPTURED_EXIT_STATUS="$__web_terminal_exit_status" \
    python3 - <<'WEB_TERMINAL_PAYLOAD_PY' 2>/dev/null
import base64
import json
import os
from datetime import datetime, timezone

payload = {
    "phase": os.environ["WEB_TERMINAL_CAPTURED_PHASE"],
    "command": os.environ["WEB_TERMINAL_CAPTURED_COMMAND"],
    "shell": os.environ["WEB_TERMINAL_CAPTURED_SHELL"],
    "cwd": os.environ.get("WEB_TERMINAL_CAPTURED_CWD") or None,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "sequence": int(os.environ["WEB_TERMINAL_CAPTURED_SEQUENCE"]),
}
exit_status = os.environ.get("WEB_TERMINAL_CAPTURED_EXIT_STATUS")
if exit_status:
    try:
        payload["exit_status"] = int(exit_status)
    except ValueError:
        payload["exit_status"] = exit_status
print(base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii"))
WEB_TERMINAL_PAYLOAD_PY
  ) || return 0
  [ -n "$__web_terminal_payload" ] || return 0
  if [ -n "${TMUX:-}" ]; then
    printf '\033Ptmux;\033\033]777;web-terminal-command;window_id=%s;payload=%s\007\033\\' "$WEB_TERMINAL_WINDOW_ID" "$__web_terminal_payload"
  else
    printf '\033]777;web-terminal-command;window_id=%s;payload=%s\007' "$WEB_TERMINAL_WINDOW_ID" "$__web_terminal_payload"
  fi
}
__web_terminal_should_capture_command() {
  [ -n "$1" ] || return 1
  case "$1" in
    WEB_TERMINAL_AUTO_RESUME=1\ *|*'&& WEB_TERMINAL_AUTO_RESUME=1 '*)
      return 1
      ;;
  esac
  return 0
}
'''
