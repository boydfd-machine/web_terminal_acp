from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectReviewConfig

DEFAULT_PR_PROVIDER = "LOCAL_CARD"
DEFAULT_MERGE_POLICY = "MANUAL"
DEFAULT_REVIEW_AGENT_PROFILE_ID = "builtin/developer"


async def get_or_create_project_review_config(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> ProjectReviewConfig:
    config = await session.scalar(
        select(ProjectReviewConfig).where(
            ProjectReviewConfig.client_id == client_id,
            ProjectReviewConfig.project_path == project_path,
        )
    )
    if config is not None:
        return config
    config = ProjectReviewConfig(client_id=client_id, project_path=project_path)
    session.add(config)
    await session.flush()
    return config


def project_review_config_values(config: ProjectReviewConfig) -> dict[str, object]:
    required_kinds = config.required_artifact_kinds_json
    return {
        "id": config.id,
        "client_id": config.client_id,
        "project_path": config.project_path,
        "pr_provider": config.pr_provider or DEFAULT_PR_PROVIDER,
        "pr_provider_config": config.pr_provider_config_json,
        "review_agent": config.review_agent,
        "review_agent_command": config.review_agent_command,
        "review_agent_profile_id": config.review_agent_profile_id or DEFAULT_REVIEW_AGENT_PROFILE_ID,
        "auto_create_review_target": config.auto_create_review_target,
        "auto_dispatch_review": config.auto_dispatch_review,
        "merge_policy": config.merge_policy or DEFAULT_MERGE_POLICY,
        "required_artifact_kinds": required_kinds if isinstance(required_kinds, list) else [],
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }
