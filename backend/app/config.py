from functools import lru_cache
import os
from pathlib import Path
import pwd

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contexts.clients.domain.server_identity import server_id_from_environment


def default_user_shell() -> str:
    shell = os.environ.get("SHELL")
    if shell:
        return shell
    try:
        return pwd.getpwuid(os.getuid()).pw_shell or "/bin/bash"
    except KeyError:
        return "/bin/bash"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    cors_allow_origins: str | None = None
    database_url: str = "postgresql+asyncpg://web_terminal:dev_password@127.0.0.1:15436/web_terminal_acp"
    db_pool_size: int = Field(default=20, ge=1)
    db_max_overflow: int = Field(default=40, ge=-1)
    db_pool_pre_ping: bool = True
    db_pool_recycle_seconds: int | None = Field(default=1800, ge=1)
    elasticsearch_url: str = "http://127.0.0.1:19201"
    tmux_pool_session: str = "web_terminal_acp_pool"
    web_terminal_server_id: str = Field(default_factory=lambda: server_id_from_environment(None))
    default_shell: str = Field(default_factory=default_user_shell)
    claude_projects_dir: str = "~/.claude/projects"
    openai_compat_base_url: str = "http://127.0.0.1:11434/v1"
    openai_compat_api_key: str = "dev-local-key"
    openai_compat_model: str = "local-summarizer"
    openai_compat_timeout_seconds: float = 60.0
    redis_url: str | None = None
    agent_event_stream_key: str = "web-terminal-acp:agent-events"
    agent_event_dead_letter_stream_key: str = "web-terminal-acp:agent-events:dead-letter"
    agent_event_consumer_group: str = "agent-event-ingest"
    agent_event_stream_maxlen: int = Field(default=50_000, ge=1)
    agent_event_worker_batch_size: int = Field(default=100, ge=1)
    agent_event_worker_block_ms: int = Field(default=1000, ge=0)
    agent_event_claim_idle_ms: int = Field(default=60_000, ge=1)
    agent_event_max_deliveries: int = Field(default=5, ge=1)
    agent_event_redis_timeout_seconds: float = Field(default=0.2, gt=0)
    ui_event_redis_channel: str = "web-terminal-acp:ui-events"
    web_terminal_auth_secret: str | None = None
    web_terminal_auth_session_ttl_seconds: int = 604800
    web_terminal_disable_auth_for_tests: bool = False
    keycloak_base_url: str | None = None
    keycloak_realm: str | None = None
    keycloak_client_id: str | None = None
    keycloak_client_secret: str | None = None
    keycloak_public_key_pem: str | None = None
    keycloak_jwks_cache_ttl_seconds: int = Field(default=300, ge=1)
    web_terminal_disable_security_rate_limits_for_tests: bool = False
    terminal_summary_idle_seconds: int = 20
    terminal_summary_initial_max_wait_seconds: int = 120
    terminal_summary_repeat_seconds: int = 600
    terminal_summary_input_context_max_bytes: int = 32768
    terminal_artifact_generation_timeout_seconds: float = Field(default=1800.0, gt=0)
    terminal_artifact_terminal_retention_seconds: float = Field(default=600.0, ge=0, le=3600)
    stale_subagent_seconds: int = Field(default=600, ge=10)
    project_todo_completion_verification_enabled: bool = True
    project_todo_completion_verification_timeout_seconds: float = Field(default=600.0, gt=0)
    project_todo_completion_verification_max_attempts: int = Field(default=2, ge=1)
    project_todo_completion_verification_background_recheck_seconds: float = Field(default=15.0, gt=0)
    tmux_window_inactive_cleanup_seconds: float = Field(default=3 * 60 * 60, ge=0)
    summary_output_language: str = "中文"
    project_todo_attachment_s3_endpoint_url: str = "/minio"
    project_todo_attachment_s3_internal_endpoint_url: str | None = None
    project_todo_attachment_s3_region: str = "us-east-1"
    project_todo_attachment_s3_bucket: str = "project-todo-attachments"
    project_todo_attachment_s3_access_key: str = "web_terminal"
    project_todo_attachment_s3_secret_key: str = "web_terminal_dev_secret"
    project_todo_attachment_presign_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    project_todo_attachment_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    project_todo_attachment_client_temp_root: str = "/tmp/web-terminal-acp/project-todo-attachments"

    @field_validator("default_shell")
    @classmethod
    def resolve_default_shell(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"", "auto", "login"}:
            return default_user_shell()
        return value

    @field_validator("web_terminal_server_id")
    @classmethod
    def resolve_web_terminal_server_id(cls, value: str) -> str:
        return server_id_from_environment(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
