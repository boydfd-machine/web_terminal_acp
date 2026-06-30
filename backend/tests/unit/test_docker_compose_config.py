from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess


def test_backend_claude_mount_uses_host_prefixed_env_var() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert re.search(r"\$\{HOST_CLAUDE_CONFIG_DIR:-[^}]+\}:/home/appuser/\.claude\b", content)
    assert re.search(r"\$\{HOST_CLAUDE_JSON:-[^}]+\}:/home/appuser/\.claude\.json\b", content)
    assert not re.search(r"\$\{CLAUDE_CONFIG_DIR:-[^}]+\}:/home/appuser/\.claude\b", content)


def test_compose_uses_stable_project_name_for_worktrees() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert content.startswith("name: ${COMPOSE_PROJECT_NAME:-web_terminal_acp}\n")


def test_compose_configures_redis_cache_and_backend_memory() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert re.search(r"^\s+redis:\n\s+image: redis:7\.2-alpine", content, flags=re.MULTILINE)
    assert "--appendonly" in content
    assert '"yes"' in content
    assert "--maxmemory-policy" in content
    assert '"noeviction"' in content
    assert '"${REDIS_MAXMEMORY:-2gb}"' in content
    assert re.search(r"redis:.*?memory: \$\{REDIS_MEMORY_LIMIT:-3G\}", content, flags=re.DOTALL)
    assert "- ./data/web_terminal_acp/redis:/data" in content
    assert "REDIS_URL: redis://redis:6379/0" in content
    assert "AGENT_EVENT_STREAM_KEY: ${AGENT_EVENT_STREAM_KEY:-web-terminal-acp:agent-events}" in content
    assert "AGENT_EVENT_DEAD_LETTER_STREAM_KEY: ${AGENT_EVENT_DEAD_LETTER_STREAM_KEY:-web-terminal-acp:agent-events:dead-letter}" in content
    assert "AGENT_EVENT_CONSUMER_GROUP: ${AGENT_EVENT_CONSUMER_GROUP:-agent-event-ingest}" in content
    assert "UI_EVENT_REDIS_CHANNEL: ${UI_EVENT_REDIS_CHANNEL:-web-terminal-acp:ui-events}" in content
    assert re.search(r"backend:.*?redis:\n\s+condition: service_healthy", content, flags=re.DOTALL)
    assert re.search(r"backend:.*?memory: 2g", content, flags=re.DOTALL)


def test_compose_runs_agent_event_worker_separately() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert re.search(r"^\s+agent-event-worker:\n", content, flags=re.MULTILINE)
    assert 'command: ["python", "-m", "app.contexts.activity.application.agent_event_worker"]' in content
    assert re.search(
        r"agent-event-worker:.*?REDIS_URL: redis://redis:6379/0",
        content,
        flags=re.DOTALL,
    )
    assert re.search(
        r"agent-event-worker:.*?redis:\n\s+condition: service_healthy",
        content,
        flags=re.DOTALL,
    )
    assert re.search(r"agent-event-worker:.*?memory: 1g", content, flags=re.DOTALL)


def test_makefile_app_recreate_includes_agent_event_worker() -> None:
    makefile = Path(__file__).resolve().parents[2].parent / "Makefile"
    content = makefile.read_text(encoding="utf-8")

    assert re.search(r"^APP_SERVICES \?= backend agent-event-worker frontend$", content, flags=re.MULTILINE)


def test_compose_uses_project_network_instead_of_legacy_links() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert "network_mode: bridge" not in content
    assert not re.search(r"^\s+links:\s*$", content, flags=re.MULTILINE)
    assert "subnet: ${COMPOSE_NETWORK_SUBNET:-10.201.0.0/24}" in content


def test_env_example_exposes_compose_network_subnet() -> None:
    env_example = Path(__file__).resolve().parents[2].parent / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    assert "COMPOSE_NETWORK_SUBNET=10.201.0.0/24" in content


def test_env_example_exposes_agent_event_queue_settings() -> None:
    env_example = Path(__file__).resolve().parents[2].parent / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    assert "AGENT_EVENT_STREAM_KEY=web-terminal-acp:agent-events" in content
    assert "AGENT_EVENT_DEAD_LETTER_STREAM_KEY=web-terminal-acp:agent-events:dead-letter" in content
    assert "AGENT_EVENT_CONSUMER_GROUP=agent-event-ingest" in content
    assert "AGENT_EVENT_STREAM_MAXLEN=50000" in content
    assert "AGENT_EVENT_WORKER_BATCH_SIZE=100" in content
    assert "AGENT_EVENT_MAX_DELIVERIES=5" in content
    assert "AGENT_EVENT_REDIS_TIMEOUT_SECONDS=0.2" in content
    assert "UI_EVENT_REDIS_CHANNEL=web-terminal-acp:ui-events" in content
    assert "REDIS_MAXMEMORY=2gb" in content
    assert "REDIS_MEMORY_LIMIT=3G" in content


def test_compose_enables_postgres_slow_query_monitoring() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert "shared_preload_libraries=pg_stat_statements" in content
    assert "pg_stat_statements.track=all" in content
    assert "track_io_timing=on" in content
    assert "log_min_duration_statement=${POSTGRES_LOG_MIN_DURATION_STATEMENT_MS:-500}" in content
    assert "checkpoint_timeout=${POSTGRES_CHECKPOINT_TIMEOUT:-15min}" in content
    assert "max_wal_size=${POSTGRES_MAX_WAL_SIZE:-2GB}" in content
    assert "log_line_prefix=%m [%p] user=%u,db=%d,app=%a,client=%h " in content
    assert "log_lock_waits=on" in content


def test_frontend_build_passes_onboarding_flag_explicitly() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert "VITE_ENABLE_ONBOARDING: ${VITE_ENABLE_ONBOARDING:-}" in content


def test_frontend_build_enables_page_annotation_by_default() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert "VITE_ENABLE_PAGE_ANNOTATION: ${VITE_ENABLE_PAGE_ANNOTATION:-true}" in content


def test_frontend_dockerfile_copies_page_annotation_vite_plugin() -> None:
    dockerfile = Path(__file__).resolve().parents[2].parent / "frontend" / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert re.search(
        r"^COPY\s+.*\bvite-plugin-page-annotation\.ts\b.*\s+\./$",
        content,
        flags=re.MULTILINE,
    )


def test_frontend_docker_context_includes_page_annotation_vite_plugin() -> None:
    dockerignore = Path(__file__).resolve().parents[2].parent / "frontend" / ".dockerignore"
    content = dockerignore.read_text(encoding="utf-8")

    assert "!vite-plugin-page-annotation.ts" in content


def test_compose_configures_minio_for_project_todo_attachments() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert re.search(r"^\s+minio:\n\s+image: \$\{MINIO_IMAGE:-minio/minio:RELEASE\.", content, flags=re.MULTILINE)
    assert "image: ${MINIO_IMAGE:-minio/minio:latest}" not in content
    assert "image: ${MINIO_MC_IMAGE:-minio/mc:latest}" not in content
    assert "restart: unless-stopped" in re.search(r"minio:.*?minio-init:", content, flags=re.DOTALL).group(0)
    assert "- ./data/web_terminal_acp/minio:/data" in content
    assert "PROJECT_TODO_ATTACHMENT_S3_ENDPOINT_URL: ${PROJECT_TODO_ATTACHMENT_S3_ENDPOINT_URL:-/minio}" in content
    assert "PROJECT_TODO_ATTACHMENT_S3_INTERNAL_ENDPOINT_URL: ${PROJECT_TODO_ATTACHMENT_S3_INTERNAL_ENDPOINT_URL:-http://minio:9000}" in content
    nginx = (compose.parent / "frontend" / "nginx" / "default.conf").read_text(encoding="utf-8")
    assert "location ^~ /minio/" in nginx
    assert "proxy_pass http://minio:9000/;" in nginx
    assert "proxy_set_header Host minio:9000;" in nginx
    vite = (compose.parent / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert '"/minio"' in vite
    assert 'target: "http://127.0.0.1:19000"' in vite
    assert "path.replace(/^\\/minio/, \"\")" in vite
    assert re.search(r"backend:.*?minio:\n\s+condition: service_healthy", content, flags=re.DOTALL)
    assert re.search(r"backend:.*?minio-init:\n\s+condition: service_completed_successfully", content, flags=re.DOTALL)
    assert 'mc mb --ignore-existing "local/$$PROJECT_TODO_ATTACHMENT_S3_BUCKET"' in content


def test_env_example_exposes_project_todo_attachment_storage_settings() -> None:
    env_example = Path(__file__).resolve().parents[2].parent / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    assert "MINIO_IMAGE=minio/minio:RELEASE." in content
    assert "MINIO_MC_IMAGE=minio/mc:RELEASE." in content
    assert "PROJECT_TODO_ATTACHMENT_S3_ENDPOINT_URL=/minio" in content
    assert "PROJECT_TODO_ATTACHMENT_S3_INTERNAL_ENDPOINT_URL=http://minio:9000" in content
    assert "PROJECT_TODO_ATTACHMENT_S3_BUCKET=project-todo-attachments" in content


def test_production_compose_keeps_data_services_private() -> None:
    compose = Path(__file__).resolve().parents[2].parent / "docker-compose.prod.yml"
    content = compose.read_text(encoding="utf-8")

    assert content.startswith("name: ${COMPOSE_PROJECT_NAME:-web_terminal_mcp}\n")
    assert "dev_password" not in content
    assert "${PROD_DATA_ROOT:-/opt/web-terminal-acp/data}/postgres" in content
    assert "${PROD_DATA_ROOT:-/opt/web-terminal-acp/data}/redis" in content
    assert "${PROD_DATA_ROOT:-/opt/web-terminal-acp/data}/elasticsearch" in content
    assert "${PROD_DATA_ROOT:-/opt/web-terminal-acp/data}/minio" in content
    assert "${FRONTEND_BIND_HOST:-0.0.0.0}:${FRONTEND_PUBLISHED_PORT:-19321}:80" in content
    assert "VITE_ENABLE_PAGE_ANNOTATION: ${VITE_ENABLE_PAGE_ANNOTATION:-false}" in content
    assert "DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}" in content
    assert "REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0" in content
    assert "--requirepass" in content
    assert "additional_contexts:" not in content
    assert "BACKEND_BASE_IMAGE: ${BACKEND_BASE_IMAGE:-web_terminal_mcp-backend-base:prod}" in content

    data_service_blocks = re.findall(
        r"^\s{2}(postgres|redis|elasticsearch|minio):\n(?:(?:^\s{4}.+\n)|\n)*",
        content,
        flags=re.MULTILINE,
    )
    assert set(data_service_blocks) == {"postgres", "redis", "elasticsearch", "minio"}
    for service in data_service_blocks:
        block = re.search(
            rf"^\s{{2}}{service}:\n(?:(?:^\s{{4}}.+\n)|\n)*",
            content,
            flags=re.MULTILINE,
        ).group(0)
        assert "\n    ports:" not in block


def test_production_env_template_documents_required_secure_values() -> None:
    env_template = Path(__file__).resolve().parents[2].parent / ".env.template"
    content = env_template.read_text(encoding="utf-8")

    assert "PROD_DEPLOY_DIR=/opt/web-terminal-acp" in content
    assert "PROD_DATA_ROOT=/opt/web-terminal-acp/data" in content
    assert "FRONTEND_BIND_HOST=0.0.0.0" in content
    assert "FRONTEND_PUBLISHED_PORT=19321" in content
    assert "PUBLIC_APP_URL=https://web-terminal.example.com" in content
    assert "CORS_ALLOW_ORIGINS=https://web-terminal.example.com" in content
    assert "KEYCLOAK_BASE_URL=https://auth.example.com" in content
    assert "KEYCLOAK_REALM=home" in content
    assert "KEYCLOAK_CLIENT_ID=web_terminal_mcp" in content
    assert "KEYCLOAK_CLIENT_SECRET=CHANGE_ME_KEYCLOAK_CLIENT_SECRET" in content
    assert "POSTGRES_PASSWORD=CHANGE_ME_GENERATED_URLSAFE_SECRET" in content
    assert "REDIS_PASSWORD=CHANGE_ME_GENERATED_URLSAFE_SECRET" in content
    assert "PROJECT_TODO_ATTACHMENT_S3_SECRET_KEY=CHANGE_ME_GENERATED_URLSAFE_SECRET" in content
    assert "WEB_TERMINAL_AUTH_SECRET=CHANGE_ME_GENERATED_URLSAFE_SECRET" in content


def test_gitea_workflows_keep_deployment_manual_and_validate_first() -> None:
    root = Path(__file__).resolve().parents[2].parent
    ci = (root / ".gitea" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    deploy = (root / ".gitea" / "workflows" / "deploy-production.yml").read_text(encoding="utf-8")

    assert "push:" in ci
    assert "pull_request:" in ci
    assert "workflow_dispatch:" not in ci
    assert "issue_comment:" in deploy
    assert "types:" in deploy
    assert "- created" in deploy
    assert "DEPLOY_COMMAND: /deploy-production web_terminal_mcp" in deploy
    assert "github.event.sender.login == 'openclaw'" in deploy
    assert "github.event.issue.number == 1" in deploy
    assert "github.event.comment.body == '/deploy-production web_terminal_mcp'" in deploy
    assert "workflow_dispatch:" not in deploy
    assert "push:" not in deploy
    assert "pull_request:" not in deploy
    assert "actions/setup-node" not in ci
    assert "actions/setup-node" not in deploy
    assert "node --version" in ci
    assert "node --version" not in deploy
    assert "test_docker_compose_config.py" in deploy
    assert "tests/integration" in ci
    assert "tests/integration" not in deploy
    assert "npm test" in ci
    assert "npm test" not in deploy
    assert "npm run build" in ci
    assert "npm run build" not in deploy
    assert "npm ci --prefer-offline --no-audit --no-fund" in ci
    assert "scripts/deploy-production.sh" in deploy
    assert re.search(r"deploy:.*?needs:\n\s+- production-gate", deploy, flags=re.DOTALL)
    assert "environment" not in deploy


def test_backend_ci_uses_runner_tmpfs_for_pytest_basetemp() -> None:
    root = Path(__file__).resolve().parents[2].parent
    ci = (root / ".gitea" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "--basetemp=/pytest-tmp/backend-unit" in ci
    assert "--basetemp=/pytest-tmp/backend-integration" in ci
    assert ci.count("test \"$(stat -f -c %T /pytest-tmp)\" = \"tmpfs\"") == 2
    assert ci.count("test \"$(df -Pm /pytest-tmp | awk 'NR == 2 {print $2}')\" -ge 4096") == 2
    assert ci.count("/pytest-tmp/web-terminal-exec-check") == 6


def test_backend_ci_system_dependencies_use_persistent_apt_cache() -> None:
    root = Path(__file__).resolve().parents[2].parent
    ci = (root / ".gitea" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    deploy = (root / ".gitea" / "workflows" / "deploy-production.yml").read_text(encoding="utf-8")
    script = (root / "scripts" / "ci" / "install-system-dependencies.sh").read_text(encoding="utf-8")

    assert ci.count("scripts/ci/install-system-dependencies.sh") == 2
    assert "scripts/ci/install-system-dependencies.sh" in deploy
    assert "apt-get update" not in ci
    assert "apt-get update" not in deploy
    assert "$HOME/.cache/uv/apt" in script
    assert "Dir::Cache::archives" in script
    assert "Dir::State::lists" in script
    assert "APT::Sandbox::User=root" in script
    assert "Keep-Downloaded-Packages" in script
    assert "apt-proxy-ubuntu" in script
    assert "default_gateway_from_proc" in script
    assert "disable_extra_apt_sources" in script


def test_backend_ci_installs_uv_from_persistent_cache_mount() -> None:
    root = Path(__file__).resolve().parents[2].parent
    ci = (root / ".gitea" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    deploy = (root / ".gitea" / "workflows" / "deploy-production.yml").read_text(encoding="utf-8")
    script = (root / "scripts" / "ci" / "install-uv.sh").read_text(encoding="utf-8")

    assert ci.count("./data/web_terminal_acp/ci-cache/uv:/ci-cache/uv") == 2
    assert "./data/web_terminal_acp/ci-cache/uv:/ci-cache/uv" in deploy
    assert ci.count("APT_CACHE_ROOT: /ci-cache/uv/apt") == 2
    assert ci.count("UV_CACHE_DIR: /ci-cache/uv/cache") == 2
    assert ci.count("UV_INSTALL_DIR: /ci-cache/uv") == 2
    assert "APT_CACHE_ROOT: /ci-cache/uv/apt" in deploy
    assert "UV_CACHE_DIR: /ci-cache/uv/cache" in deploy
    assert "UV_INSTALL_DIR: /ci-cache/uv" in deploy
    assert ci.count('mkdir -p "$APT_CACHE_ROOT" "$UV_CACHE_DIR" "$UV_INSTALL_DIR/bin"') == 2
    assert 'mkdir -p "$APT_CACHE_ROOT" "$UV_CACHE_DIR" "$UV_INSTALL_DIR/bin"' in deploy
    assert ci.count("bash scripts/ci/install-uv.sh") == 2
    assert "bash scripts/ci/install-uv.sh" in deploy
    assert "curl -LsSf https://astral.sh/uv/install.sh" not in ci
    assert "curl -LsSf https://astral.sh/uv/install.sh" not in deploy
    assert ci.count("mountpoint -q /ci-cache/uv") == 2
    assert "mountpoint -q /ci-cache/uv" in deploy
    assert 'env -u UV_INSTALL_DIR UV_UNMANAGED_INSTALL="$UV_INSTALL_DIR/bin"' in script
    assert '[[ -x "$UV_INSTALL_DIR/bin/uv" ]]' in script
    assert 'echo "$UV_INSTALL_DIR/bin" >> "$GITHUB_PATH"' in script
    assert "flock" in script


def test_production_deploy_script_updates_legacy_frontend_loopback_bind_host(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2].parent
    script = root / "scripts" / "deploy-production.sh"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "COMPOSE_PROJECT_NAME=web_terminal_mcp",
                "PROD_DEPLOY_DIR=/opt/web-terminal-acp",
                "FRONTEND_BIND_HOST=127.0.0.1",
                "FRONTEND_PUBLISHED_PORT=19321",
                "",
            ]
        ),
        encoding="utf-8",
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"${1:-}\" = \"run\" ]; then cat >/dev/null; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    result = subprocess.run(
        ["bash", "-c", f"source {shlex.quote(str(script))}; ensure_frontend_bind_host"],
        cwd=root,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "PROD_ENV_FILE": str(env_file),
            "PROD_DEPLOY_DIR": str(tmp_path / "deploy"),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    content = env_file.read_text(encoding="utf-8")
    assert "FRONTEND_BIND_HOST=0.0.0.0" in content
    assert "FRONTEND_BIND_HOST=127.0.0.1" not in content


def test_production_deploy_script_sets_frontend_bind_host_before_docker_work() -> None:
    root = Path(__file__).resolve().parents[2].parent
    content = (root / "scripts" / "deploy-production.sh").read_text(encoding="utf-8")

    assert 'PROD_FRONTEND_BIND_HOST="${PROD_FRONTEND_BIND_HOST:-0.0.0.0}"' in content
    assert 'chown --reference="$PROD_ENV_FILE" "$tmp"' in content
    assert re.search(
        r"main\(\) \{\n\s+require_env_file\n\s+ensure_frontend_bind_host\n\s+docker version >/dev/null",
        content,
    )
