from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.workspace.api.schemas import ProjectSummaryOut
from app.contexts.workspace.application.project_summarizer import (
    ProjectSummarizer,
    collect_project_summary_context,
)
from app.contexts.workspace.domain.project_summaries import ProjectSummaryRequest
from app.contexts.workspace.infrastructure.project_summaries_repository import (
    list_project_summaries,
    mark_project_summary_failed,
    mark_project_summary_running,
    mark_project_summary_succeeded,
    upsert_project_summary_pending,
)
from app.models import Client, ProjectSummary

ProjectSummarizerFactory = Callable[[], ProjectSummarizer]


class ProjectSummaryApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ProjectSummaryApiService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        summarizer_factory: ProjectSummarizerFactory = ProjectSummarizer,
    ) -> None:
        self._session = session
        self._summarizer_factory = summarizer_factory

    async def list_summaries(self, client_id: UUID) -> list[ProjectSummaryOut]:
        await self._require_client(client_id)
        summaries = await list_project_summaries(self._session, client_id)
        return [project_summary_out(summary) for summary in summaries]

    async def summarize_project(
        self,
        client_id: UUID,
        request: ProjectSummaryRequest,
    ) -> ProjectSummaryOut:
        await self._require_client(client_id)
        summary = await self._prepare_summary(client_id, request.project_path)

        try:
            context = await collect_project_summary_context(
                self._session,
                client_id,
                request.project_path,
            )
            result = await self._summarizer_factory().summarize(
                context,
                output_language=request.output_language,
            )
            await mark_project_summary_succeeded(self._session, summary, result.name)
            await self._session.commit()
            await self._session.refresh(summary)
        except Exception as exc:
            await mark_project_summary_failed(self._session, summary, str(exc))
            await self._session.commit()
            await self._session.refresh(summary)
            raise ProjectSummaryApiError(
                502,
                f"project summarization failed: {exc}",
            ) from exc

        return project_summary_out(summary)

    async def _prepare_summary(self, client_id: UUID, project_path: str) -> ProjectSummary:
        summary = await upsert_project_summary_pending(self._session, client_id, project_path)
        await self._session.commit()
        await mark_project_summary_running(self._session, summary)
        await self._session.commit()
        return summary

    async def _require_client(self, client_id: UUID) -> Client:
        client = await get_client(self._session, client_id)
        if client is None:
            raise ProjectSummaryApiError(404, "client not found")
        return client


def project_summary_out(summary: ProjectSummary) -> ProjectSummaryOut:
    return ProjectSummaryOut(
        project_path=summary.project_path,
        display_name=summary.display_name,
        status=summary.status.value,
        last_error=summary.last_error,
        updated_at=summary.updated_at,
    )
