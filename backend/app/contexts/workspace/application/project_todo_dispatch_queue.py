from __future__ import annotations

from app.models import ProjectTodo
from app.platform.common_schemas import AgentLaunchIn


def prepare_project_todo_queued_dispatch(
    todo: ProjectTodo,
    *,
    agent_launch: AgentLaunchIn,
    prompt: str,
    output_language: str | None,
) -> None:
    todo.assigned_window_id = None
    todo.assigned_agent = agent_launch.agent
    todo.agent_profile_id = agent_launch.profile_id
    todo.dispatch_prompt = prompt
    todo.dispatch_output_language = output_language
    todo.dispatch_stage = None
    todo.dispatch_error = None
    todo.dispatched_at = None
    todo.awaiting_review_at = None
    todo.completed_at = None
    todo.review_status = "NOT_REQUESTED"
    todo.review_window_id = None
    todo.review_prompt = None
    todo.review_dispatched_at = None
    todo.reviewed_at = None
    todo.review_unseen = False
    todo.needs_human_review = False
    todo.implementation_worktree_json = None
