import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from elastic_transport import TransportError
from elasticsearch import ApiError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.auth import AuthMiddleware
from app.platform.logging_config import configure_logging
from app.contexts.activity.api import (
    terminal_notifications_routes,
    terminal_recents_routes,
    traces_routes,
    work_status_routes,
)
from app.contexts.agent_profiles.api import routes as agent_profiles_routes
from app.contexts.agent_profiles.api import import_export_routes as agent_profile_import_export_routes
from app.contexts.agent_profiles.api import system_config_routes
from app.contexts.clients.api import client_agent as client_agent_routes
from app.contexts.clients.api import routes as clients_routes
from app.contexts.clients.application.client_lookup import ensure_local_client
from app.contexts.mcp_acp.api import agent_ops_project_todos_routes, routes as mcp_acp_routes
from app.contexts.terminal_artifacts.api import routes as terminal_artifacts_routes
from app.contexts.terminal_artifacts.application import reconcile_interrupted_terminal_artifacts
from app.contexts.terminal_artifacts.application.dispatch_compensation import (
    run_artifact_dispatch_compensation_loop,
)
from app.contexts.terminal_runtime import api as terminal_routes
from app.contexts.terminal_runtime.api import aux_terminal_routes
from app.contexts.terminal_runtime.application.offline_monitor import (
    mark_all_remote_clients_disconnected,
    run_offline_monitor_loop,
)
from app.contexts.terminal_runtime.application.window_reconciler import (
    mark_missing_tmux_windows_error,
)
from app.contexts.terminal_runtime.infrastructure.tmux_manager import get_tmux_manager
from app.contexts.windows import api as windows_routes
from app.contexts.workspace.api import (
    folders_routes,
    project_agent_preferences_routes,
    project_file_search_routes,
    project_review_configs_routes,
    project_summaries_routes,
    project_todo_annotations_routes,
    project_todo_attachments_routes,
    project_todo_artifact_cards_routes,
    project_todo_artifact_links_routes,
    project_todo_history_routes,
    project_todo_reviews_routes,
    project_todo_types_routes,
    project_todos_routes,
    projects_routes,
)
from app.contexts.workspace.application.folder_split_worker import run_folder_split_job_worker_loop
from app.contexts.workspace.application.summary_worker import run_summary_job_worker_loop
from app.contexts.workspace.application.project_todo_periodic_scheduler import (
    run_project_todo_periodic_scheduler_loop,
)
from app.contexts.workspace.application.project_todo_review_dispatch import run_project_todo_auto_review_loop
from app.contexts.workspace.application.project_todo_worktree_reconciler import (
    run_project_todo_worktree_reconciliation_loop,
)
from app.db import SessionLocal
from app.platform import auth_routes, search_routes, ui_events_routes, ui_settings_routes
from app.platform.plugins.artifact_plugins import routes as artifact_plugin_routes
from app.platform.plugins.artifact_plugins import preview_session_routes as artifact_plugin_preview_routes
from app.platform.ingest.claude_watcher import poll_claude_jsonl_directory
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.platform.csrf import CsrfProtectionMiddleware
from app.platform.search_index import ensure_indexes, get_es_client
from app.platform.security_rate_limit import SecurityRateLimitMiddleware
from app.platform.ui_event_bridge import run_redis_ui_event_bridge
from app.platform.ui_events import UiEventHub
from app.version import __version__

logger = logging.getLogger(__name__)

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = get_es_client()
    if getattr(app.state, "ui_event_hub", None) is None:
        app.state.ui_event_hub = UiEventHub()
    if getattr(app.state, "client_connections", None) is None:
        app.state.client_connections = ClientConnectionRegistry()
    if getattr(app.state, "terminal_broker", None) is None:
        from app.contexts.terminal_runtime.application.broker import TerminalBroker

        app.state.terminal_broker = TerminalBroker()
    app.state.es_client = client
    app.state.es_indexes_ready = False
    app.state.es_startup_error = None

    try:
        await ensure_indexes(client)
        app.state.es_indexes_ready = True
    except (ApiError, TransportError) as exc:
        app.state.es_startup_error = exc

    async with SessionLocal() as session:
        await ensure_local_client(session)
        disconnected_count = await mark_all_remote_clients_disconnected(session)
        interrupted_artifact_count = await reconcile_interrupted_terminal_artifacts(session)
        await session.commit()
        if disconnected_count:
            logger.info(
                "marked remote clients offline on startup",
                extra={"marked_count": disconnected_count},
            )
        if interrupted_artifact_count:
            logger.info(
                "marked interrupted terminal artifacts failed on startup",
                extra={"marked_count": interrupted_artifact_count},
            )

    await mark_missing_tmux_windows_error(SessionLocal, get_tmux_manager())

    background_tasks = [
        asyncio.create_task(
            poll_claude_jsonl_directory(
                SessionLocal,
                Path(settings.claude_projects_dir),
                es_client=app.state.es_client,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(
            run_summary_job_worker_loop(
                SessionLocal,
                es_client=app.state.es_client,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(
            run_folder_split_job_worker_loop(
                SessionLocal,
                es_client=app.state.es_client,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(
            run_project_todo_auto_review_loop(
                SessionLocal,
                tmux_manager=get_tmux_manager(),
                registry=app.state.client_connections,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(
            run_project_todo_periodic_scheduler_loop(
                SessionLocal,
                tmux_manager=get_tmux_manager(),
                registry=app.state.client_connections,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(
            run_project_todo_worktree_reconciliation_loop(
                SessionLocal,
                registry=app.state.client_connections,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(
            run_artifact_dispatch_compensation_loop(
                SessionLocal,
                tmux_manager=get_tmux_manager(),
                terminal_broker=app.state.terminal_broker,
                registry=app.state.client_connections,
                ui_event_hub=app.state.ui_event_hub,
            )
        ),
        asyncio.create_task(run_offline_monitor_loop(SessionLocal, ui_event_hub=app.state.ui_event_hub)),
    ]
    if settings.redis_url:
        background_tasks.append(
            asyncio.create_task(
                run_redis_ui_event_bridge(
                    app.state.ui_event_hub,
                    redis_url=settings.redis_url,
                    channel=settings.ui_event_redis_channel,
                )
            )
        )
    app.state.background_tasks = background_tasks

    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        results = await asyncio.gather(*background_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(
                    "background task stopped with error",
                    exc_info=(type(result), result, result.__traceback__),
                )
        await client.close()


settings = get_settings()


def _cors_allow_origins() -> list[str]:
    configured = settings.cors_allow_origins
    if configured is None or not configured.strip():
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="Web Terminal ACP", version=__version__, lifespan=lifespan)
app.state.client_connections = ClientConnectionRegistry()
app.state.ui_event_hub = UiEventHub()
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityRateLimitMiddleware)
app.add_middleware(CsrfProtectionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_routes.router)
app.include_router(system_config_routes.router)
app.include_router(agent_profile_import_export_routes.router)
app.include_router(agent_profiles_routes.router)
app.include_router(aux_terminal_routes.router)
app.include_router(client_agent_routes.router)
app.include_router(clients_routes.router)
app.include_router(mcp_acp_routes.router)
app.include_router(mcp_acp_routes.agent_ops_router)
app.include_router(agent_ops_project_todos_routes.router)
app.include_router(folders_routes.router)
app.include_router(windows_routes.router)
app.include_router(projects_routes.router)
app.include_router(project_agent_preferences_routes.router)
app.include_router(project_file_search_routes.router)
app.include_router(project_review_configs_routes.router)
app.include_router(project_todo_reviews_routes.router)
app.include_router(project_todo_artifact_cards_routes.router)
app.include_router(project_todo_artifact_links_routes.router)
app.include_router(project_todo_types_routes.router)
app.include_router(project_todo_history_routes.router)
app.include_router(project_todos_routes.router)
app.include_router(project_todo_annotations_routes.router)
app.include_router(project_todo_attachments_routes.router)
app.include_router(project_summaries_routes.router)
app.include_router(terminal_recents_routes.router)
app.include_router(terminal_recents_routes.global_router)
app.include_router(terminal_artifacts_routes.router)
app.include_router(artifact_plugin_routes.router)
app.include_router(artifact_plugin_preview_routes.router)
app.include_router(terminal_notifications_routes.router)
app.include_router(work_status_routes.router)
app.include_router(terminal_routes.router)
app.include_router(search_routes.router)
app.include_router(traces_routes.router)
app.include_router(ui_settings_routes.router)
app.include_router(ui_events_routes.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
