from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.workspace.application import project_todo_dispatch
from app.contexts.workspace.application import project_todo_dispatch_prompt


def test_build_project_todo_prompt_keeps_parent_card_context_separate() -> None:
    parent = project_todo_dispatch.ProjectTodoPromptReference(
        title="Build API",
        sessions=[
            project_todo_dispatch.ProjectTodoPromptSession(
                role="implementation",
                terminal_id="terminal-1",
                terminal_title="API terminal",
                turns=[
                    project_todo_dispatch.ProjectTodoPromptTurn(
                        user_input="Build endpoints from card description",
                        last_agent_output="Implemented stable endpoints",
                    )
                ],
            )
        ],
    )

    prompt = project_todo_dispatch.build_project_todo_prompt(
        project_path="/workspace",
        title="Wire child UI",
        description="Use the parent API card.",
        parent_todo=parent,
        referenced_todos=[
            project_todo_dispatch.ProjectTodoPromptReference(title="Prepare data"),
        ],
    )

    assert "# Parent card" in prompt
    assert "# References" in prompt
    assert prompt.index("# Parent card") < prompt.index("# References")
    assert "## Build API Card" in prompt
    assert "Build endpoints from card description" in prompt
    assert "## Prepare data Card" in prompt


def test_build_project_todo_prompt_limits_overlong_parent_agent_records() -> None:
    long_user_input = "USER_HEAD " + ("u" * 120_000) + " USER_TAIL"
    long_agent_output = "AGENT_HEAD " + ("a" * 120_000) + " AGENT_TAIL"
    child_description = "CHILD_HEAD " + ("c" * 100_000) + " CHILD_TAIL"

    prompt = project_todo_dispatch.build_project_todo_prompt(
        project_path="/workspace",
        title="Wire child UI",
        description=child_description,
        parent_todos=[
            project_todo_dispatch.ProjectTodoPromptReference(
                title="Parent with huge records",
                todo_id="parent-1",
                sessions=[
                    project_todo_dispatch.ProjectTodoPromptSession(
                        role="implementation",
                        terminal_id="terminal-1",
                        terminal_title="Huge terminal",
                        turns=[
                            project_todo_dispatch.ProjectTodoPromptTurn(
                                user_input=f"{long_user_input} turn {index}",
                                last_agent_output=f"{long_agent_output} turn {index}",
                            )
                            for index in range(12)
                        ],
                    )
                ],
            )
        ],
    )

    assert "Todo: Wire child UI" in prompt
    assert "CHILD_HEAD" in prompt
    assert "CHILD_TAIL" in prompt
    assert "## Parent with huge records Card" in prompt
    assert "USER_HEAD" in prompt
    assert "AGENT_TAIL" in prompt
    assert "[truncated " in prompt
    assert "showing most recent" in prompt
    assert len(prompt) < 125_000


@pytest.mark.asyncio
async def test_build_dispatch_prompt_includes_full_parent_chain(monkeypatch) -> None:
    client_id = uuid4()
    current_id = uuid4()
    parent_id = uuid4()
    grandparent_id = uuid4()
    great_grandparent_id = uuid4()
    current = SimpleNamespace(
        id=current_id,
        parent_todo_id=parent_id,
        title="Implement child card",
        description="Use the hierarchy.",
        todo_type_id="default",
        artifact_kinds_json=None,
    )
    parent = SimpleNamespace(
        id=parent_id,
        parent_todo_id=grandparent_id,
        title="Parent card",
    )
    grandparent = SimpleNamespace(
        id=grandparent_id,
        parent_todo_id=great_grandparent_id,
        title="Grandparent card",
    )
    great_grandparent = SimpleNamespace(
        id=great_grandparent_id,
        parent_todo_id=None,
        title="Great grandparent card",
    )
    todos_by_id = {
        parent_id: parent,
        grandparent_id: grandparent,
        great_grandparent_id: great_grandparent,
    }

    async def fake_referenced_project_todos_for_todos(_session, _todos):
        return {}

    async def fake_parent_project_todos_for_todos(_session, todos):
        return {
            todo.parent_todo_id: todos_by_id[todo.parent_todo_id]
            for todo in todos
            if todo.parent_todo_id in todos_by_id
        }

    async def fake_get_project_todo_type(*_args, **_kwargs):
        return SimpleNamespace(dispatch_template=None)

    async def fake_prompt_references_for_project_todos(_session, todos):
        return [
            project_todo_dispatch.ProjectTodoPromptReference(
                title=todo.title,
                todo_id=str(todo.id),
            )
            for todo in todos
        ]

    monkeypatch.setattr(
        project_todo_dispatch_prompt,
        "referenced_project_todos_for_todos",
        fake_referenced_project_todos_for_todos,
    )
    monkeypatch.setattr(
        project_todo_dispatch_prompt,
        "parent_project_todos_for_todos",
        fake_parent_project_todos_for_todos,
    )
    monkeypatch.setattr(project_todo_dispatch_prompt, "get_project_todo_type", fake_get_project_todo_type)
    monkeypatch.setattr(
        project_todo_dispatch_prompt,
        "prompt_references_for_project_todos",
        fake_prompt_references_for_project_todos,
    )

    prompt = await project_todo_dispatch_prompt.build_dispatch_prompt_for_project_todo(
        object(),
        client_id=client_id,
        project_path="/workspace",
        todo=current,
        payload_prompt=None,
    )

    assert "# Parent card hierarchy" in prompt
    assert f"Current todo -> Parent card (todo id: {parent_id})" in prompt
    assert f"Parent card (todo id: {parent_id}) -> Grandparent card (todo id: {grandparent_id})" in prompt
    assert (
        f"Grandparent card (todo id: {grandparent_id}) "
        f"-> Great grandparent card (todo id: {great_grandparent_id})"
    ) in prompt
    assert "Relationship: direct parent of current todo." in prompt
    assert f"Relationship: parent of Parent card (todo id: {parent_id}); grandparent of current todo." in prompt
    assert (
        f"Relationship: parent of Grandparent card (todo id: {grandparent_id}); "
        "great-grandparent of current todo."
    ) in prompt


@pytest.mark.asyncio
async def test_build_dispatch_prompt_limits_parent_agent_record_context(monkeypatch) -> None:
    client_id = uuid4()
    current_id = uuid4()
    parent_id = uuid4()
    current = SimpleNamespace(
        id=current_id,
        parent_todo_id=parent_id,
        title="Implement child card",
        description="Use the parent without losing this child request.",
        todo_type_id="default",
        artifact_kinds_json=None,
    )
    parent = SimpleNamespace(
        id=parent_id,
        parent_todo_id=None,
        title="Parent card with many records",
    )
    long_user_input = "PARENT_USER_HEAD " + ("u" * 120_000) + " PARENT_USER_TAIL"
    long_agent_output = "PARENT_AGENT_HEAD " + ("a" * 120_000) + " PARENT_AGENT_TAIL"

    async def fake_referenced_project_todos_for_todos(_session, _todos):
        return {}

    async def fake_parent_project_todos_for_todos(_session, todos):
        return {parent_id: parent} if any(todo.parent_todo_id == parent_id for todo in todos) else {}

    async def fake_get_project_todo_type(*_args, **_kwargs):
        return SimpleNamespace(dispatch_template=None)

    async def fake_prompt_references_for_project_todos(_session, todos):
        return [
            project_todo_dispatch.ProjectTodoPromptReference(
                title=todo.title,
                todo_id=str(todo.id),
                sessions=[
                    project_todo_dispatch.ProjectTodoPromptSession(
                        role="implementation",
                        terminal_id="terminal-1",
                        terminal_title="Parent terminal",
                        turns=[
                            project_todo_dispatch.ProjectTodoPromptTurn(
                                user_input=f"{long_user_input} turn {index}",
                                last_agent_output=f"{long_agent_output} turn {index}",
                            )
                            for index in range(12)
                        ],
                    )
                ],
            )
            for todo in todos
        ]

    monkeypatch.setattr(
        project_todo_dispatch_prompt,
        "referenced_project_todos_for_todos",
        fake_referenced_project_todos_for_todos,
    )
    monkeypatch.setattr(
        project_todo_dispatch_prompt,
        "parent_project_todos_for_todos",
        fake_parent_project_todos_for_todos,
    )
    monkeypatch.setattr(project_todo_dispatch_prompt, "get_project_todo_type", fake_get_project_todo_type)
    monkeypatch.setattr(
        project_todo_dispatch_prompt,
        "prompt_references_for_project_todos",
        fake_prompt_references_for_project_todos,
    )

    prompt = await project_todo_dispatch_prompt.build_dispatch_prompt_for_project_todo(
        object(),
        client_id=client_id,
        project_path="/workspace",
        todo=current,
        payload_prompt=None,
    )

    assert "Todo: Implement child card" in prompt
    assert "Use the parent without losing this child request." in prompt
    assert "## Parent card with many records Card" in prompt
    assert "PARENT_USER_HEAD" in prompt
    assert "PARENT_AGENT_TAIL" in prompt
    assert "[truncated " in prompt
    assert len(prompt) < 90_000
