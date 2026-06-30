from app.client_agent.client_daemon import start_client_daemon_command


def test_start_client_daemon_command_prefers_process_supervisors_and_falls_back_to_tmux():
    command = start_client_daemon_command(
        install_path="/home/alice/.web-terminal-acp/servers/primary",
        app_path="/home/alice/.web-terminal-acp/servers/primary/app",
        python_path="/home/alice/.web-terminal-acp/servers/primary/venv/bin/python",
        config_path="/home/alice/.web-terminal-acp/servers/primary/config.json",
        daemon_name="web_terminal_acp_client_primary",
        npm_bin_path="/home/alice/.web-terminal-acp/servers/primary/npm-global/bin",
    )

    assert "Restart=always" in command
    assert "RestartSec=5" in command
    assert "systemctl --user enable --now web_terminal_acp_client_primary.service" in command
    assert "<key>KeepAlive</key>" in command
    assert "launchctl bootstrap gui/$(id -u)" in command
    assert "'$HOME/Library/LaunchAgents" not in command
    assert "tmux new-session -d -s web_terminal_acp_client_primary" in command
    assert "client.stdout.log" in command
    assert "PYTHONPATH=/home/alice/.web-terminal-acp/servers/primary/app" in command
    assert "--config /home/alice/.web-terminal-acp/servers/primary/config.json" in command
