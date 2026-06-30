# ruff: noqa: F401
from uuid import uuid4

import pytest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base

from app.models import ClientRuntime, TerminalArtifact, TerminalArtifactStatus

from app.repositories.clients import create_client

from app.repositories.terminal_artifacts import create_terminal_artifact

from app.contexts.windows.infrastructure.repository import create_window

from app.services.runtime.broker import TerminalBroker

from app.services.runtime.types import RuntimeWindow

from app.services.terminal_artifacts import (
    _ArtifactOutputCollector,
    _agent_terminal_is_ready,
    _artifact_prompt_with_output_language,
    _artifact_terminal_retention_seconds,
    _cleanup_ephemeral_window,
    _create_ephemeral_window,
    _mark_generation_failed,
    _publish_artifact_invalidation,
    _read_artifact_output_file,
    _resolve_source_agent_command,
    _run_artifact_prompt,
    _wait_before_ephemeral_window_cleanup,
    reconcile_interrupted_terminal_artifacts,
    TerminalArtifactGenerationRequest,
)

import app.services.terminal_artifacts as terminal_artifact_service


def unused_session_factory():
    raise AssertionError("session factory should not be used")


__all__ = [name for name in globals() if not name.startswith("__")]
