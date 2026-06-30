from __future__ import annotations

from app.contexts.activity.application.terminal_work_status import to_work_status_out
from app.contexts.windows.application.assigned_terminal_summary import AssignedTerminalSummary
from app.contexts.workspace.api.schemas import (
    ProjectTodoAssignedTerminalOut,
    ProjectTodoArtifactOut,
    ProjectTodoListItemOut,
    ProjectTodoOut,
    ProjectTodoReferenceOut,
    ProjectTodoRelationOut,
    ProjectTodoRunOut,
)
from app.contexts.workspace.api.project_todo_attachment_schemas import ProjectTodoAttachmentOut
from app.contexts.workspace.api.project_todo_type_projection import project_todo_type_out
from app.contexts.workspace.application.project_todo_dependencies import ProjectTodoDependencyGraph
from app.models import (
    ProjectTodo,
    ProjectTodoArtifact,
    ProjectTodoAttachment,
    ProjectTodoRun,
    ProjectTodoStatus,
    ProjectTodoType,
    TerminalArtifact,
)


def project_todo_out(
    todo: ProjectTodo,
    todo_type: ProjectTodoType,
    artifacts: list[tuple[ProjectTodoArtifact, TerminalArtifact]] | None = None,
    attachments: list[ProjectTodoAttachment] | None = None,
    graph: ProjectTodoDependencyGraph | None = None,
    referenced_todos: list[ProjectTodo] | None = None,
    parent_todo: ProjectTodo | None = None,
    child_todos: list[ProjectTodo] | None = None,
    assigned_terminal: AssignedTerminalSummary | None = None,
    execution_runs: list[ProjectTodoRun] | None = None,
    run_terminals: dict | None = None,
    artifact_terminals: dict | None = None,
) -> ProjectTodoOut:
    return ProjectTodoOut(
        id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        todo_type_id=todo.todo_type_id,
        todo_type=project_todo_type_out(todo_type),
        parent_todo_id=todo.parent_todo_id,
        parent_todo=_todo_relation_out(parent_todo) if parent_todo is not None else None,
        title=todo.title,
        description=todo.description,
        status=todo.status.value,
        sort_order=todo.sort_order,
        assigned_window_id=todo.assigned_window_id,
        assigned_agent=todo.assigned_agent,
        agent_profile_id=todo.agent_profile_id,
        dispatch_prompt=todo.dispatch_prompt,
        dispatch_stage=_project_todo_dispatch_stage_out(todo),
        dispatch_error=todo.dispatch_error,
        blocked_reason=todo.blocked_reason,
        dispatched_at=todo.dispatched_at,
        awaiting_review_at=todo.awaiting_review_at,
        completed_at=todo.completed_at,
        review_strategy=todo.review_strategy,
        review_status=todo.review_status,
        review_agent=todo.review_agent,
        review_agent_profile_id=todo.review_agent_profile_id,
        review_window_id=todo.review_window_id,
        review_prompt=todo.review_prompt,
        review_dispatched_at=todo.review_dispatched_at,
        reviewed_at=todo.reviewed_at,
        review_unseen=todo.review_unseen,
        needs_human_review=todo.needs_human_review,
        review_notes=todo.review_notes,
        implementation_worktree=todo.implementation_worktree_json,
        execution_kind=todo.execution_kind,
        terminal_policy=todo.terminal_policy,
        trigger_strategy=todo.trigger_strategy,
        cron_expression=todo.cron_expression,
        schedule_enabled=todo.schedule_enabled,
        next_trigger_at=todo.next_trigger_at,
        last_triggered_at=todo.last_triggered_at,
        execution_run_count=todo.execution_run_count,
        artifact_kinds=todo.artifact_kinds_json or [],
        input_artifact_ids=todo.input_artifact_ids_json or [],
        artifact_model_selection=todo.artifact_model_selection_json,
        assigned_terminal=_assigned_terminal_out(assigned_terminal),
        execution_runs=[
            _todo_run_out(run, run_terminals.get(run.window_id) if run.window_id is not None and run_terminals else None)
            for run in execution_runs or []
        ],
        attachments=[project_todo_attachment_out(attachment) for attachment in attachments or []],
        artifacts=[
            _todo_artifact_out(
                link,
                artifact,
                artifact_terminals.get(artifact.ephemeral_window_id)
                if artifact.ephemeral_window_id is not None and artifact_terminals
                else None,
            )
            for link, artifact in artifacts or []
        ],
        dependencies=[_todo_relation_out(summary) for summary in (graph.dependencies.get(todo.id, []) if graph else [])],
        dependents=[_todo_relation_out(summary) for summary in (graph.dependents.get(todo.id, []) if graph else [])],
        child_todos=[_todo_relation_out(child) for child in child_todos or []],
        referenced_todos=[_todo_reference_out(referenced_todo) for referenced_todo in referenced_todos or []],
        queued_dispatch=todo.id in graph.queued_dispatches if graph else False,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
    )


def project_todo_list_item_out(
    todo: ProjectTodo,
    todo_type: ProjectTodoType,
    artifacts: list[tuple[ProjectTodoArtifact, TerminalArtifact]] | None = None,
    attachments: list[ProjectTodoAttachment] | None = None,
    *,
    parent_todo: ProjectTodo | None = None,
    child_todos: list[ProjectTodo] | None = None,
    referenced_todos: list[ProjectTodo] | None = None,
    assigned_terminal: AssignedTerminalSummary | None = None,
    execution_runs: list[ProjectTodoRun] | None = None,
    run_terminals: dict | None = None,
    artifact_terminals: dict | None = None,
    queued_dispatch: bool = False,
) -> ProjectTodoListItemOut:
    return ProjectTodoListItemOut(
        id=todo.id,
        client_id=todo.client_id,
        project_path=todo.project_path,
        todo_type_id=todo.todo_type_id,
        todo_type=project_todo_type_out(todo_type),
        parent_todo_id=todo.parent_todo_id,
        parent_todo=_todo_relation_out(parent_todo) if parent_todo is not None else None,
        title=todo.title,
        status=todo.status.value,
        sort_order=todo.sort_order,
        assigned_window_id=todo.assigned_window_id,
        assigned_agent=todo.assigned_agent,
        agent_profile_id=todo.agent_profile_id,
        dispatch_stage=_project_todo_dispatch_stage_out(todo),
        dispatch_error=todo.dispatch_error,
        blocked_reason=todo.blocked_reason,
        awaiting_review_at=todo.awaiting_review_at,
        review_status=todo.review_status,
        review_unseen=todo.review_unseen,
        needs_human_review=todo.needs_human_review,
        implementation_worktree=todo.implementation_worktree_json,
        artifact_kinds=todo.artifact_kinds_json or [],
        execution_kind=todo.execution_kind,
        terminal_policy=todo.terminal_policy,
        trigger_strategy=todo.trigger_strategy,
        cron_expression=todo.cron_expression,
        schedule_enabled=todo.schedule_enabled,
        execution_run_count=todo.execution_run_count,
        assigned_terminal=_assigned_terminal_out(assigned_terminal),
        execution_runs=[
            _todo_run_out(run, run_terminals.get(run.window_id) if run.window_id is not None and run_terminals else None)
            for run in execution_runs or []
        ],
        input_artifact_ids=todo.input_artifact_ids_json or [],
        artifact_model_selection=todo.artifact_model_selection_json,
        attachments=[project_todo_attachment_out(attachment) for attachment in attachments or []],
        artifacts=[
            _todo_artifact_out(
                link,
                artifact,
                artifact_terminals.get(artifact.ephemeral_window_id)
                if artifact.ephemeral_window_id is not None and artifact_terminals
                else None,
            )
            for link, artifact in artifacts or []
        ],
        child_todos=[_todo_relation_out(child) for child in child_todos or []],
        referenced_todos=[_todo_reference_out(referenced_todo) for referenced_todo in referenced_todos or []],
        queued_dispatch=queued_dispatch,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
    )


def _project_todo_dispatch_stage_out(todo: ProjectTodo) -> str | None:
    if todo.status not in {ProjectTodoStatus.todo, ProjectTodoStatus.dispatched}:
        return None
    return todo.dispatch_stage


def _todo_run_out(
    run: ProjectTodoRun,
    assigned_terminal: AssignedTerminalSummary | None = None,
) -> ProjectTodoRunOut:
    return ProjectTodoRunOut(
        id=run.id,
        todo_id=run.project_todo_id,
        window_id=run.window_id,
        run_number=run.run_number,
        trigger_strategy=run.trigger_strategy,
        trigger_reason=run.trigger_reason,
        terminal_policy=run.terminal_policy,
        dispatch_mode=run.dispatch_mode,
        prompt=run.prompt,
        status=run.status,
        started_at=run.started_at,
        dispatched_at=run.dispatched_at,
        completed_at=run.completed_at,
        last_error=run.last_error,
        assigned_terminal=_assigned_terminal_out(assigned_terminal),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _todo_artifact_out(
    link: ProjectTodoArtifact,
    artifact: TerminalArtifact,
    artifact_terminal: AssignedTerminalSummary | None = None,
) -> ProjectTodoArtifactOut:
    return ProjectTodoArtifactOut(
        id=link.id,
        artifact_id=artifact.id,
        client_id=artifact.client_id,
        window_id=artifact.virtual_window_id,
        source_window_id=artifact.source_window_id,
        ephemeral_window_id=artifact.ephemeral_window_id,
        review_run_id=link.review_run_id,
        created_by_window_id=link.created_by_window_id,
        artifact_scope=artifact.artifact_scope,
        project_path=artifact.project_path,
        title=artifact.title,
        artifact_kind=artifact.artifact_kind,
        status=artifact.status.value,
        purpose=link.purpose,
        agent_name=_artifact_agent_name(artifact_terminal),
        agent_status=to_work_status_out(artifact_terminal.work_status) if artifact_terminal is not None else None,
        metadata_json=artifact.metadata_json,
        last_error=artifact.last_error,
        started_at=artifact.started_at,
        completed_at=artifact.completed_at,
        created_at=link.created_at,
        updated_at=artifact.updated_at,
    )


def project_todo_attachment_out(attachment: ProjectTodoAttachment) -> ProjectTodoAttachmentOut:
    return ProjectTodoAttachmentOut(
        id=attachment.id,
        todo_id=attachment.project_todo_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        status=attachment.status,
        uploaded_at=attachment.uploaded_at,
        created_at=attachment.created_at,
        updated_at=attachment.updated_at,
    )


def _todo_relation_out(summary) -> ProjectTodoRelationOut:
    return ProjectTodoRelationOut(
        id=summary.id,
        title=summary.title,
        status=summary.status.value,
        completed_at=summary.completed_at,
    )


def _todo_reference_out(todo: ProjectTodo) -> ProjectTodoReferenceOut:
    return ProjectTodoReferenceOut(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        status=todo.status.value,
    )


def _assigned_terminal_out(summary: AssignedTerminalSummary | None) -> ProjectTodoAssignedTerminalOut | None:
    if summary is None:
        return None
    return ProjectTodoAssignedTerminalOut(
        id=summary.id,
        title=summary.title,
        summary=summary.summary,
        title_tags=summary.title_tags,
        runtime_tags=summary.runtime_tags,
        work_status=to_work_status_out(summary.work_status),
        topic_path=summary.topic_path,
        git_worktree=summary.git_worktree,
        parent_window_id=summary.parent_window_id,
        root_window_id=summary.root_window_id,
        derived_mode=summary.derived_mode,
        created_at=summary.created_at,
    )


def _artifact_agent_name(summary: AssignedTerminalSummary | None) -> str | None:
    if summary is None:
        return None
    for tag in summary.runtime_tags:
        if tag and not tag.startswith("/"):
            return tag
    return summary.title
