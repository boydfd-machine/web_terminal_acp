# ruff: noqa: F403,F405
from tests.unit.test_shell_hook_command_support import *

def test_bash_managed_shell_command_contains_command_capture_hook() -> None:
    managed = build_managed_shell_command(
        shell="/bin/bash",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is True
    assert managed.hook_script is not None
    assert 'PATH="$HOME/.web-terminal-acp/npm-global/bin:$PATH"' in managed.command
    assert "WEB_TERMINAL_CLIENT_ID=12345678-1234-5678-1234-567812345678" in managed.command
    assert "WEB_TERMINAL_WINDOW_ID=87654321-4321-8765-4321-876543218765" in managed.command
    assert "WEB_TERMINAL_SERVER_URL=https://control.example.com" in managed.command
    assert "WEB_TERMINAL_COMMAND_HOOK=1" in managed.command
    assert "WEB_TERMINAL_PROJECT_PATH=/workspace/project" in managed.command
    assert "WEB_TERMINAL_CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_CLAUDE_CODE_HOME='~/.web-terminal-acp/claude-code-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_CURSOR_HOME='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_ANTIGRAVITY_HOME='~/.web-terminal-acp/antigravity-cli-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME='~/.web-terminal-acp/antigravity-cli-homes/.managed-home/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_ORIGINAL_CODEX_HOME='~/.codex'" in managed.command
    assert "WEB_TERMINAL_ORIGINAL_CLAUDE_CODE_HOME='~/.claude'" in managed.command
    assert "WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME='~/.gemini/antigravity-cli'" in managed.command
    assert "WEB_TERMINAL_ANTIGRAVITY_CACHE_HOME=" not in managed.command
    assert " CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'" not in managed.command
    assert not managed.command.startswith("CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'")
    assert "CLAUDE_CONFIG_DIR='~/.web-terminal-acp/claude-code-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "CURSOR_AGENT_HOME='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WT_B" in managed.command
    assert len(managed.command) < 12000
    hook_script = managed.hook_script
    assert '__web_terminal_source_codex_home="${WEB_TERMINAL_ORIGINAL_CODEX_HOME:-${CODEX_HOME:-$HOME/.codex}}"' in hook_script
    assert '__web_terminal_source_codex_home="$HOME/${__web_terminal_source_codex_home#"~/"}"' in hook_script
    assert "export CODEX_HOME=\"$WEB_TERMINAL_CODEX_HOME\"" in hook_script
    assert "__web_terminal_mark_codex_folder_trusted" in hook_script
    assert "__web_terminal_mark_cursor_folder_trusted" in hook_script
    assert shell_loop_items(hook_script, "__web_terminal_codex_item") == {
        "auth.json",
        "config.toml",
        "AGENTS.md",
        "plugin_marketplaces.json",
        "hooks",
        "hooks.json",
        "hooks.disabled.json",
        "mcp.json",
        "mcp.disabled.json",
    }
    assert shell_loop_items(hook_script, "__web_terminal_codex_tree_item") == {
        "skills",
        "skills.disabled",
        "plugins",
        "plugins.disabled",
    }
    assert "for __web_terminal_codex_history_item in history.json history.jsonl" in hook_script
    assert "export CLAUDE_CONFIG_DIR=\"$WEB_TERMINAL_CLAUDE_CODE_HOME\"" in hook_script
    assert '__web_terminal_source_claude_home="${WEB_TERMINAL_ORIGINAL_CLAUDE_CODE_HOME:-$HOME/.claude}"' in hook_script
    assert '__web_terminal_source_claude_home="$HOME/${__web_terminal_source_claude_home#"~/"}"' in hook_script
    assert "__web_terminal_source_claude_json=\"${WEB_TERMINAL_ORIGINAL_CLAUDE_JSON:-$HOME/.claude.json}\"" in hook_script
    assert '__web_terminal_source_claude_json="$HOME/${__web_terminal_source_claude_json#"~/"}"' in hook_script
    assert "ln -s \"$__web_terminal_source_claude_json\" \"$WEB_TERMINAL_CLAUDE_CODE_HOME/.claude.json\"" in hook_script
    assert shell_loop_items(hook_script, "__web_terminal_claude_item") == {
        "settings.json",
        "settings.local.json",
        ".claude.json",
        "commands",
        "api-key-helper.sh",
        "hooks",
        "hooks.json",
        "hooks.disabled.json",
        "mcp.json",
        "mcp.disabled.json",
    }
    assert shell_loop_items(hook_script, "__web_terminal_claude_tree_item") == {
        "skills",
        "skills.disabled",
        "plugins",
        "plugins.disabled",
    }
    assert "for __web_terminal_claude_history_item in history.json history.jsonl file-history" in hook_script
    assert "__web_terminal_load_claude_settings_env \"$__web_terminal_source_claude_home/settings.json\"" in hook_script
    assert "json.load(open(sys.argv[1], encoding=\"utf-8\")).get(\"env\", {})" in hook_script
    assert "__web_terminal_prepare_claude_code_home" in hook_script
    assert "export CURSOR_AGENT_HOME=\"$managed_cursor\"" in hook_script
    assert "export CURSOR_CONFIG_DIR=\"$managed_cursor\"" in hook_script
    assert "export CURSOR_DATA_DIR=\"$managed_cursor\"" in hook_script
    assert "__wt_prepare_agent_home" in hook_script
    assert "__web_terminal_prepare_agent_homes" not in hook_script
    assert "__web_terminal_prepare_agent_command_path" in hook_script
    assert '"~/.web-terminal-acp/npm-global/bin" "~/.local/bin" "~/.npm-global/bin"' in hook_script
    assert '"~/.bun/bin" "~/.cargo/bin" "/opt/homebrew/bin" "/usr/local/bin"' in hook_script
    assert "__web_terminal_load_user_shell_env" in hook_script
    assert "__web_terminal_load_zshrc_env" in hook_script
    assert "__web_terminal_missing_claude_env" in hook_script
    assert '[ -n "${ANTHROPIC_BASE_URL:-}" ] || [ -n "${CLAUDE_CODE_API_BASE_URL:-}" ] || return 0' in hook_script
    assert "if __web_terminal_missing_claude_env; then" in hook_script
    assert "zsh -ic" in hook_script
    assert "ANTHROPIC_*=*|CLAUDE_CODE_*=*" in hook_script
    assert "CLAUDE_CONFIG_DIR=*" not in hook_script
    assert "__web_terminal_prepare_cursor_home" in hook_script
    assert "__web_terminal_prepare_cursor_skill_home" in hook_script
    assert "__web_terminal_run_cursor_agent_command" in hook_script
    assert "agent|cursor|cursor-agent)" in hook_script
    assert "__web_terminal_prepare_antigravity_home" in hook_script
    assert "WEB_TERMINAL_ANTIGRAVITY_CACHE_HOME=\"$cache_home\"" in hook_script
    assert 'XDG_CACHE_HOME="$WEB_TERMINAL_ANTIGRAVITY_CACHE_HOME"' in hook_script
    assert 'WEB_TERMINAL_ANTIGRAVITY_PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$cache_home/ms-playwright-go}"' in hook_script
    assert 'PLAYWRIGHT_BROWSERS_PATH="$WEB_TERMINAL_ANTIGRAVITY_PLAYWRIGHT_BROWSERS_PATH"' in hook_script
    assert "alias agy-p=" in hook_script
    assert "__web_terminal_run_agent_command_with_permission agy-p --dangerously-skip-permissions" in hook_script
    assert "__web_terminal_install_agent_permission_wrappers" in hook_script
    assert "__web_terminal_run_agent_command_with_permission codex --dangerously-bypass-approvals-and-sandbox" in hook_script
    assert "__web_terminal_run_agent_command_with_permission claude --dangerously-skip-permissions" in hook_script
    assert "command agent" in hook_script
    assert "command cursor" in hook_script
    assert "command \"$__web_terminal_command_name\"" in hook_script
    assert "CURSOR_CONFIG_DIR=" in hook_script
    assert "CURSOR_DATA_DIR=" in hook_script
    assert "PROMPT_COMMAND" in hook_script
    assert "__web_terminal_start_bash_command" in hook_script
    assert " DEBUG" in hook_script
    assert "__web_terminal_last_history_id" in hook_script
    assert "__web_terminal_finish_bash_command" in hook_script
    assert "__web_terminal_should_capture_command" in hook_script
    assert "WEB_TERMINAL_AUTO_RESUME=1" in hook_script
    assert "WEB_TERMINAL_CAPTURED_CWD" in hook_script
    assert "web-terminal-command" in hook_script
    assert "Ptmux" in hook_script
    assert "phase" in hook_script
    assert "payload=" in hook_script
    assert "exec /bin/bash" in managed.command

def test_zsh_managed_shell_command_contains_preexec_command_capture_hook() -> None:
    managed = build_managed_shell_command(
        shell="/bin/zsh",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is True
    assert managed.hook_script is not None
    assert 'PATH="$HOME/.web-terminal-acp/npm-global/bin:$PATH"' in managed.command
    assert "WEB_TERMINAL_COMMAND_HOOK=1" in managed.command
    assert "WEB_TERMINAL_PROJECT_PATH=/workspace/project" in managed.command
    assert "WEB_TERMINAL_CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_CLAUDE_CODE_HOME='~/.web-terminal-acp/claude-code-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_CURSOR_HOME='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_ANTIGRAVITY_HOME='~/.web-terminal-acp/antigravity-cli-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WEB_TERMINAL_ORIGINAL_CODEX_HOME='~/.codex'" in managed.command
    assert "WEB_TERMINAL_ORIGINAL_CLAUDE_CODE_HOME='~/.claude'" in managed.command
    assert " CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'" not in managed.command
    assert not managed.command.startswith("CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'")
    assert "CLAUDE_CONFIG_DIR='~/.web-terminal-acp/claude-code-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "CURSOR_AGENT_HOME='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'" in managed.command
    assert "WT_Z" in managed.command
    assert len(managed.command) < 12000
    hook_script = managed.hook_script
    assert '__web_terminal_source_codex_home="${WEB_TERMINAL_ORIGINAL_CODEX_HOME:-${CODEX_HOME:-$HOME/.codex}}"' in hook_script
    assert "export CODEX_HOME=\"$WEB_TERMINAL_CODEX_HOME\"" in hook_script
    assert "__web_terminal_mark_codex_folder_trusted" in hook_script
    assert "__web_terminal_mark_cursor_folder_trusted" in hook_script
    assert "__web_terminal_prepare_claude_code_home" in hook_script
    assert "__wt_prepare_agent_home" in hook_script
    assert "__web_terminal_prepare_agent_homes" not in hook_script
    assert "__web_terminal_prepare_agent_command_path" in hook_script
    assert "__web_terminal_prepare_cursor_home" in hook_script
    assert "__web_terminal_prepare_cursor_skill_home" in hook_script
    assert "__web_terminal_run_cursor_agent_command" in hook_script
    assert "agent|cursor|cursor-agent)" in hook_script
    assert "__web_terminal_prepare_antigravity_home" in hook_script
    assert "__web_terminal_install_agent_permission_wrappers" in hook_script
    assert "__web_terminal_run_agent_command_with_permission codex --dangerously-bypass-approvals-and-sandbox" in hook_script
    assert "__web_terminal_run_agent_command_with_permission claude --dangerously-skip-permissions" in hook_script
    assert "CURSOR_CONFIG_DIR=" in hook_script
    assert "CURSOR_DATA_DIR=" in hook_script
    assert "preexec()" in hook_script
    assert "precmd()" in hook_script
    assert "__web_terminal_pending_command" in hook_script
    assert "__web_terminal_emit_command_marker started zsh" in hook_script
    assert "__web_terminal_emit_command_marker finished zsh" in hook_script
    assert "__web_terminal_should_capture_command" in hook_script
    assert "WEB_TERMINAL_AUTO_RESUME=1" in hook_script
    assert "WEB_TERMINAL_CAPTURED_CWD" in hook_script
    assert "web-terminal-command" in hook_script
    assert "Ptmux" in hook_script
    assert "exec /bin/zsh" in managed.command

def test_managed_shell_command_exports_agent_ops_token_when_provided() -> None:
    managed = build_managed_shell_command(
        shell="/bin/bash",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
        agent_ops_token="ops-token",
    )

    assert "WEB_TERMINAL_AGENT_OPS_TOKEN=ops-token" in managed.command

def test_common_command_capture_hook_emits_marker_without_python_311_datetime_utc(tmp_path) -> None:
    script = f"""
set -e
{_common_hook_script()}
__web_terminal_emit_command_marker started bash 7 "" pwd
"""
    env = {
        "HOME": str(tmp_path),
        "PATH": os.environ["PATH"],
        "WEB_TERMINAL_WINDOW_ID": str(WINDOW_ID),
        "WEB_TERMINAL_CODEX_HOME": "~/.web-terminal-acp/codex-homes/window-1",
        "WEB_TERMINAL_CLAUDE_CODE_HOME": "~/.web-terminal-acp/claude-code-homes/window-1",
        "WEB_TERMINAL_ORIGINAL_CLAUDE_JSON": "~/.claude.json",
        "WEB_TERMINAL_CURSOR_HOME": "~/.web-terminal-acp/cursor-homes/window-1",
    }

    result = subprocess.run(
        ["bash", "-c", script],
        check=False,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "web-terminal-command" in result.stdout
    assert "payload=" in result.stdout
    assert "from datetime import UTC" not in script
    assert "timezone.utc" in script

def test_unsupported_shell_returns_fallback_command_and_unsupported_flag() -> None:
    managed = build_managed_shell_command(
        shell="/usr/bin/fish",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is False
    assert managed.command.startswith('PATH="$HOME/.web-terminal-acp/npm-global/bin:$PATH" ')
    assert "/bin/sh -c " in managed.command
    for assignment in (
        "WEB_TERMINAL_CLIENT_ID=12345678-1234-5678-1234-567812345678",
        "WEB_TERMINAL_WINDOW_ID=87654321-4321-8765-4321-876543218765",
        "WEB_TERMINAL_SERVER_URL=https://control.example.com",
        "WEB_TERMINAL_COMMAND_HOOK=1",
        "WEB_TERMINAL_PROJECT_PATH=/workspace/project",
        "WEB_TERMINAL_CODEX_HOME='~/.web-terminal-acp/codex-homes/87654321-4321-8765-4321-876543218765'",
        "WEB_TERMINAL_CLAUDE_CODE_HOME='~/.web-terminal-acp/claude-code-homes/87654321-4321-8765-4321-876543218765'",
        "WEB_TERMINAL_CURSOR_HOME='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'",
        "WEB_TERMINAL_ANTIGRAVITY_HOME='~/.web-terminal-acp/antigravity-cli-homes/87654321-4321-8765-4321-876543218765'",
        "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME='~/.web-terminal-acp/antigravity-cli-homes/.managed-home/87654321-4321-8765-4321-876543218765'",
        "WEB_TERMINAL_ORIGINAL_CODEX_HOME='~/.codex'",
        "WEB_TERMINAL_ORIGINAL_CLAUDE_CODE_HOME='~/.claude'",
        "WEB_TERMINAL_ORIGINAL_CLAUDE_JSON='~/.claude.json'",
        "WEB_TERMINAL_ORIGINAL_CURSOR_DIR='~/.cursor'",
        "WEB_TERMINAL_ORIGINAL_ANTIGRAVITY_CLI_HOME='~/.gemini/antigravity-cli'",
        "WEB_TERMINAL_ORIGINAL_HOME='~'",
        "CLAUDE_CONFIG_DIR='~/.web-terminal-acp/claude-code-homes/87654321-4321-8765-4321-876543218765'",
        "CURSOR_AGENT_HOME='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'",
        "CURSOR_CONFIG_DIR='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'",
        "CURSOR_DATA_DIR='~/.web-terminal-acp/cursor-homes/87654321-4321-8765-4321-876543218765'",
    ):
        assert assignment in managed.command
    assert "__wt_prepare_agent_home" in managed.command
    assert "__web_terminal_prepare_agent_homes" not in managed.command
    assert "__web_terminal_load_zshrc_env" in managed.command
    assert "exec /usr/bin/fish" in managed.command
    assert "web-terminal-command" not in managed.command

def test_direct_codex_shell_command_adds_permission_flag() -> None:
    managed = build_managed_shell_command(
        shell="codex resume codex-session",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is False
    assert "codex --dangerously-bypass-approvals-and-sandbox resume codex-session || __web_terminal_agent_exit=$?" in managed.command
    assert "agent command exited with status" in managed.command
    assert "__web_terminal_prepare_direct_agent_launch codex" in managed.command
    assert "__web_terminal_load_user_shell_env" in managed.command
    assert "__web_terminal_load_zshrc_env" in managed.command

def test_direct_claude_shell_command_adds_permission_flag() -> None:
    managed = build_managed_shell_command(
        shell="claude --resume claude-session",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is False
    assert "__web_terminal_run_claude_code_command --dangerously-skip-permissions --resume claude-session || __web_terminal_agent_exit=$?" in managed.command
    assert "agent command exited with status" in managed.command
    assert "__web_terminal_prepare_direct_agent_launch claude" in managed.command
    assert "__web_terminal_load_zshrc_env" in managed.command

def test_managed_shell_enables_claude_code_metrics_only_telemetry_when_endpoint_set() -> None:
    managed = build_managed_shell_command(
        shell="/bin/bash",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
        agent_otel_metrics_endpoint="http://127.0.0.1:43181/v1/metrics",
    )

    assert "WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT=http://127.0.0.1:43181/v1/metrics" in managed.command
    assert "OTEL_LOGS_EXPORTER" not in managed.command
    hook_script = managed.hook_script
    assert hook_script is not None
    assert "__web_terminal_run_claude_code_command" in hook_script
    assert "CLAUDE_CODE_ENABLE_TELEMETRY=1" in hook_script
    assert "OTEL_METRICS_EXPORTER=otlp" in hook_script
    assert "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/json" in hook_script
    assert "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=\"$WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT\"" in hook_script
    assert "OTEL_RESOURCE_ATTRIBUTES=\"${OTEL_RESOURCE_ATTRIBUTES:+$OTEL_RESOURCE_ATTRIBUTES,}web_terminal.client_id=$WEB_TERMINAL_CLIENT_ID,web_terminal.window_id=$WEB_TERMINAL_WINDOW_ID\"" in hook_script
    assert "__web_terminal_run_claude_code_command" in hook_script

def test_direct_claude_shell_command_enables_metrics_only_telemetry_when_endpoint_set() -> None:
    managed = build_managed_shell_command(
        shell="claude --resume claude-session",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
        agent_otel_metrics_endpoint="http://127.0.0.1:43181/v1/metrics",
    )

    assert "WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT=http://127.0.0.1:43181/v1/metrics" in managed.command
    assert "OTEL_LOGS_EXPORTER" not in managed.command
    assert "__web_terminal_run_claude_code_command --dangerously-skip-permissions --resume claude-session || __web_terminal_agent_exit=$?" in managed.command
    assert "claude --dangerously-skip-permissions --resume claude-session || __web_terminal_agent_exit=$?" not in managed.command

def test_direct_claude_fallback_shell_keeps_command_wrappers_and_metrics_endpoint(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = home / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (bin_dir / "claude").chmod(0o755)

    managed = build_managed_shell_command(
        shell="claude --version",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        agent_otel_metrics_endpoint="http://127.0.0.1:43181/v1/metrics",
    )
    result = subprocess.run(
        ["/bin/sh", "-c", managed.command],
        check=False,
        env={
            "HOME": str(home),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "SHELL": "/bin/zsh",
        },
        input=(
            'printf "WT_OTEL=%s\\n" "${WEB_TERMINAL_CLAUDE_OTEL_METRICS_ENDPOINT:-}"\n'
            "command -v __web_terminal_run_claude_code_command >/dev/null "
            "&& echo WT_CLAUDE_WRAPPER=yes || echo WT_CLAUDE_WRAPPER=no\n"
            "exit\n"
        ),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "WT_OTEL=http://127.0.0.1:43181/v1/metrics" in result.stdout
    assert "WT_CLAUDE_WRAPPER=yes" in result.stdout

def test_direct_cursor_agent_shell_command_preserves_arguments() -> None:
    managed = build_managed_shell_command(
        shell="agent --resume cursor-session",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is False
    assert "agent --resume cursor-session || __web_terminal_agent_exit=$?" in managed.command
    assert "agent command exited with status" in managed.command
    assert "__web_terminal_prepare_direct_agent_launch agent" in managed.command

def test_direct_proxychains_cursor_agent_shell_command_is_agent_launch() -> None:
    managed = build_managed_shell_command(
        shell="proxychains4 -q agent",
        client_id=CLIENT_ID,
        window_id=WINDOW_ID,
        server_url=SERVER_URL,
        project_path="/workspace/project",
    )

    assert managed.command_capture_supported is False
    assert "proxychains4 -q agent || __web_terminal_agent_exit=$?" in managed.command
    assert "agent command exited with status" in managed.command
    assert "__web_terminal_prepare_direct_agent_launch agent" in managed.command

def test_direct_agent_commands_find_user_local_executables(tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    for command_name in ("codex", "claude", "agent", "agy-p"):
        executable = bin_dir / command_name
        executable.write_text(
            "#!/bin/sh\n"
            f"printf '{command_name}:%s:%s:%s\\n' \"$1\" \"$OPENAI_API_KEY\" \"$HOME\"\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "OPENAI_API_KEY": "codex-key",
    }
    command_cases = [
        (
            "codex --version",
            f"codex:--dangerously-bypass-approvals-and-sandbox:codex-key:{home}",
        ),
        ("claude --version", f"claude:--dangerously-skip-permissions:codex-key:{home}"),
        ("agent --version", f"agent:--version:codex-key:{home}"),
        (
            "agy-p --version",
            "agy-p:--dangerously-skip-permissions:codex-key:"
            f"{home}/.web-terminal-acp/antigravity-cli-homes/.managed-home/{WINDOW_ID}",
        ),
    ]

    for shell, expected in command_cases:
        managed = build_managed_shell_command(
            shell=shell,
            client_id=CLIENT_ID,
            window_id=WINDOW_ID,
            server_url=SERVER_URL,
        )
        result = subprocess.run(
            ["/bin/sh", "-c", managed.command],
            check=False,
            env=env,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert expected in result.stdout
        assert "agent command exited with status 0" in result.stdout
