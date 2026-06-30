from __future__ import annotations

from app.contexts.workspace.api.schemas import ProjectTodoTypeOut
from app.models import ProjectTodoType


def project_todo_type_out(todo_type: ProjectTodoType) -> ProjectTodoTypeOut:
    return ProjectTodoTypeOut(
        id=todo_type.id,
        scope=todo_type.scope,
        client_id=todo_type.client_id,
        project_path=todo_type.project_path,
        name=todo_type.name,
        description=todo_type.description,
        agent=todo_type.agent,
        agent_profile_id=todo_type.agent_profile_id,
        artifact_kinds=todo_type.artifact_kinds_json or [],
        input_artifact_ids=todo_type.input_artifact_ids_json or [],
        dispatch_template=todo_type.dispatch_template,
        created_at=todo_type.created_at,
        updated_at=todo_type.updated_at,
    )
