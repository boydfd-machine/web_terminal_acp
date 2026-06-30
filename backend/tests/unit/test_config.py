import os
from pathlib import Path

from app.config import Settings, get_settings


SETTINGS_ENV_VARS = (
    "APP_HOST",
    "APP_PORT",
    "CORS_ALLOW_ORIGINS",
    "DATABASE_URL",
    "ELASTICSEARCH_URL",
    "TMUX_POOL_SESSION",
    "WEB_TERMINAL_SERVER_ID",
    "DEFAULT_SHELL",
    "CLAUDE_PROJECTS_DIR",
    "OPENAI_COMPAT_BASE_URL",
    "OPENAI_COMPAT_API_KEY",
    "OPENAI_COMPAT_MODEL",
    "REDIS_URL",
    "AGENT_EVENT_STREAM_KEY",
    "AGENT_EVENT_DEAD_LETTER_STREAM_KEY",
    "AGENT_EVENT_CONSUMER_GROUP",
    "AGENT_EVENT_STREAM_MAXLEN",
    "AGENT_EVENT_WORKER_BATCH_SIZE",
    "AGENT_EVENT_WORKER_BLOCK_MS",
    "AGENT_EVENT_CLAIM_IDLE_MS",
    "AGENT_EVENT_MAX_DELIVERIES",
    "AGENT_EVENT_REDIS_TIMEOUT_SECONDS",
    "SUMMARY_OUTPUT_LANGUAGE",
    "WEB_TERMINAL_AUTH_SECRET",
    "WEB_TERMINAL_AUTH_SESSION_TTL_SECONDS",
    "KEYCLOAK_BASE_URL",
    "KEYCLOAK_REALM",
    "KEYCLOAK_CLIENT_ID",
    "KEYCLOAK_CLIENT_SECRET",
    "KEYCLOAK_PUBLIC_KEY_PEM",
    "KEYCLOAK_JWKS_CACHE_TTL_SECONDS",
    "WEB_TERMINAL_DISABLE_SECURITY_RATE_LIMITS_FOR_TESTS",
    "TERMINAL_ARTIFACT_GENERATION_TIMEOUT_SECONDS",
    "TERMINAL_ARTIFACT_TERMINAL_RETENTION_SECONDS",
    "PROJECT_TODO_ATTACHMENT_S3_ENDPOINT_URL",
    "PROJECT_TODO_ATTACHMENT_S3_INTERNAL_ENDPOINT_URL",
    "PROJECT_TODO_ATTACHMENT_S3_REGION",
    "PROJECT_TODO_ATTACHMENT_S3_BUCKET",
    "PROJECT_TODO_ATTACHMENT_S3_ACCESS_KEY",
    "PROJECT_TODO_ATTACHMENT_S3_SECRET_KEY",
    "PROJECT_TODO_ATTACHMENT_PRESIGN_TTL_SECONDS",
    "PROJECT_TODO_ATTACHMENT_MAX_BYTES",
    "PROJECT_TODO_ATTACHMENT_CLIENT_TEMP_ROOT",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_PRE_PING",
    "DB_POOL_RECYCLE_SECONDS",
)


def clear_settings_env(monkeypatch):
    get_settings.cache_clear()
    settings_env_var_names = {env_var.lower() for env_var in SETTINGS_ENV_VARS}
    for env_var in list(os.environ):
        if env_var.lower() in settings_env_var_names:
            monkeypatch.delenv(env_var, raising=False)


def test_clear_settings_env_removes_case_insensitive_variants(monkeypatch):
    monkeypatch.setenv("app_host", "0.0.0.0")
    monkeypatch.setenv("app_port", "1234")
    monkeypatch.setenv("openai_compat_model", "from-env")

    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8000
    assert settings.openai_compat_model == "local-summarizer"


def test_clear_settings_env_removes_mixed_case_variants(monkeypatch):
    monkeypatch.setenv("App_Host", "0.0.0.0")
    monkeypatch.setenv("App_Port", "1234")
    monkeypatch.setenv("OpenAI_Compat_Model", "from-env")

    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8000
    assert settings.openai_compat_model == "local-summarizer"


def test_settings_defaults_bind_locally(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")

    settings = Settings(_env_file=None)

    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8000
    assert settings.default_shell == "/usr/bin/zsh"


def test_settings_default_shell_auto_uses_user_shell(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")

    settings = Settings(_env_file=None, default_shell="auto")

    assert settings.default_shell == "/usr/bin/zsh"


def test_settings_default_shell_can_be_forced(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")

    settings = Settings(_env_file=None, default_shell="/bin/bash")

    assert settings.default_shell == "/bin/bash"


def test_settings_accept_server_id_env(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("WEB_TERMINAL_SERVER_ID", " primary-control ")

    settings = Settings(_env_file=None)

    assert settings.web_terminal_server_id == "primary-control"


def test_settings_empty_server_id_env_falls_back_to_hostname(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("WEB_TERMINAL_SERVER_ID", "")
    monkeypatch.setattr(
        "app.contexts.clients.domain.server_identity.socket.gethostname",
        lambda: "server-host",
    )

    settings = Settings(_env_file=None)

    assert settings.web_terminal_server_id == "server-host"


def test_settings_env_file_points_to_project_root():
    project_root = Path(__file__).resolve().parents[3]

    assert Settings.model_config["env_file"] == project_root / ".env"


def test_settings_accept_openai_compatible_fields(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(
        _env_file=None,
        openai_compat_base_url="http://127.0.0.1:11434/v1",
        openai_compat_api_key="key",
        openai_compat_model="model-a",
    )
    assert settings.openai_compat_base_url == "http://127.0.0.1:11434/v1"
    assert settings.openai_compat_api_key == "key"
    assert settings.openai_compat_model == "model-a"


def test_settings_default_summary_output_language(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.summary_output_language == "中文"


def test_settings_accept_summary_output_language(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("SUMMARY_OUTPUT_LANGUAGE", "English")

    settings = Settings(_env_file=None)

    assert settings.summary_output_language == "English"


def test_settings_accept_redis_url(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://redis:6379/0"


def test_settings_default_agent_event_queue_timeout_is_short(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.agent_event_redis_timeout_seconds == 0.2


def test_settings_default_agent_event_stream_retention_fits_local_redis(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.agent_event_stream_maxlen == 50_000


def test_settings_accept_agent_event_queue_settings(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("AGENT_EVENT_STREAM_KEY", "events")
    monkeypatch.setenv("AGENT_EVENT_DEAD_LETTER_STREAM_KEY", "events:dead")
    monkeypatch.setenv("AGENT_EVENT_CONSUMER_GROUP", "workers")
    monkeypatch.setenv("AGENT_EVENT_STREAM_MAXLEN", "123")
    monkeypatch.setenv("AGENT_EVENT_WORKER_BATCH_SIZE", "12")
    monkeypatch.setenv("AGENT_EVENT_WORKER_BLOCK_MS", "34")
    monkeypatch.setenv("AGENT_EVENT_CLAIM_IDLE_MS", "56")
    monkeypatch.setenv("AGENT_EVENT_MAX_DELIVERIES", "7")
    monkeypatch.setenv("AGENT_EVENT_REDIS_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("UI_EVENT_REDIS_CHANNEL", "ui-events")

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.agent_event_stream_key == "events"
    assert settings.agent_event_dead_letter_stream_key == "events:dead"
    assert settings.agent_event_consumer_group == "workers"
    assert settings.agent_event_stream_maxlen == 123
    assert settings.agent_event_worker_batch_size == 12
    assert settings.agent_event_worker_block_ms == 34
    assert settings.agent_event_claim_idle_ms == 56
    assert settings.agent_event_max_deliveries == 7
    assert settings.agent_event_redis_timeout_seconds == 0.5
    assert settings.ui_event_redis_channel == "ui-events"


def test_settings_accept_auth_secret(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("WEB_TERMINAL_AUTH_SECRET", "login-secret")
    monkeypatch.setenv("WEB_TERMINAL_AUTH_SESSION_TTL_SECONDS", "30")

    settings = Settings(_env_file=None)

    assert settings.web_terminal_auth_secret == "login-secret"
    assert settings.web_terminal_auth_session_ttl_seconds == 30


def test_settings_accept_keycloak_and_cors(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173")
    monkeypatch.setenv("KEYCLOAK_BASE_URL", "https://auth.example.com")
    monkeypatch.setenv("KEYCLOAK_REALM", "home")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "web_terminal")
    monkeypatch.setenv("KEYCLOAK_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("KEYCLOAK_PUBLIC_KEY_PEM", "pem")
    monkeypatch.setenv("KEYCLOAK_JWKS_CACHE_TTL_SECONDS", "60")

    settings = Settings(_env_file=None)

    assert settings.cors_allow_origins == "http://127.0.0.1:5173"
    assert settings.keycloak_base_url == "https://auth.example.com"
    assert settings.keycloak_realm == "home"
    assert settings.keycloak_client_id == "web_terminal"
    assert settings.keycloak_client_secret == "client-secret"
    assert settings.keycloak_public_key_pem == "pem"
    assert settings.keycloak_jwks_cache_ttl_seconds == 60


def test_settings_accept_security_rate_limit_test_switch(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("WEB_TERMINAL_DISABLE_SECURITY_RATE_LIMITS_FOR_TESTS", "true")

    settings = Settings(_env_file=None)

    assert settings.web_terminal_disable_security_rate_limits_for_tests is True


def test_settings_default_terminal_artifact_generation_timeout(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.terminal_artifact_generation_timeout_seconds == 1800.0


def test_settings_accept_terminal_artifact_generation_timeout(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ARTIFACT_GENERATION_TIMEOUT_SECONDS", "3600")

    settings = Settings(_env_file=None)

    assert settings.terminal_artifact_generation_timeout_seconds == 3600.0


def test_settings_default_terminal_artifact_terminal_retention(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.terminal_artifact_terminal_retention_seconds == 600.0


def test_settings_accept_terminal_artifact_terminal_retention(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ARTIFACT_TERMINAL_RETENTION_SECONDS", "120")

    settings = Settings(_env_file=None)

    assert settings.terminal_artifact_terminal_retention_seconds == 120.0


def test_settings_accept_project_todo_attachment_storage(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("PROJECT_TODO_ATTACHMENT_S3_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("PROJECT_TODO_ATTACHMENT_S3_INTERNAL_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("PROJECT_TODO_ATTACHMENT_S3_BUCKET", "todo-images")
    monkeypatch.setenv("PROJECT_TODO_ATTACHMENT_MAX_BYTES", "1024")

    settings = Settings(_env_file=None)

    assert settings.project_todo_attachment_s3_endpoint_url == "https://s3.example.com"
    assert settings.project_todo_attachment_s3_internal_endpoint_url == "http://minio:9000"
    assert settings.project_todo_attachment_s3_bucket == "todo-images"
    assert settings.project_todo_attachment_max_bytes == 1024


def test_settings_default_project_todo_attachment_public_endpoint_uses_frontend_proxy(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.project_todo_attachment_s3_endpoint_url == "/minio"
    assert settings.project_todo_attachment_s3_internal_endpoint_url is None


def test_settings_db_pool_defaults_cover_concurrent_load(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.db_pool_size == 20
    assert settings.db_max_overflow == 40
    assert settings.db_pool_pre_ping is True
    assert settings.db_pool_recycle_seconds == 1800


def test_settings_db_pool_accepts_env_overrides(monkeypatch):
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("DB_POOL_SIZE", "8")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "16")
    monkeypatch.setenv("DB_POOL_PRE_PING", "false")
    monkeypatch.setenv("DB_POOL_RECYCLE_SECONDS", "600")

    settings = Settings(_env_file=None)

    assert settings.db_pool_size == 8
    assert settings.db_max_overflow == 16
    assert settings.db_pool_pre_ping is False
    assert settings.db_pool_recycle_seconds == 600
