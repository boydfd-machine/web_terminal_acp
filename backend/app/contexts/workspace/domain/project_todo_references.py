from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

PROJECT_TODO_REFERENCE_RE = re.compile(r"@\[ *(?:其他需求|其它需求) *[：:] *\$(?P<body>[^\]\r\n]+?) *\]")
PROJECT_TODO_REFERENCE_ID_RE = re.compile(
    r"^(?P<title>.*?)\s*\|\s*(?P<todo_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)


@dataclass(frozen=True)
class ProjectTodoReferenceRequest:
    title: str
    todo_id: UUID | None = None


def project_todo_reference_titles(description: str | None) -> list[str]:
    return [request.title for request in project_todo_reference_requests(description) if request.todo_id is None]


def project_todo_reference_requests(description: str | None) -> list[ProjectTodoReferenceRequest]:
    if not description:
        return []

    requests: list[ProjectTodoReferenceRequest] = []
    seen: set[tuple[str, UUID | None]] = set()
    for match in PROJECT_TODO_REFERENCE_RE.finditer(description):
        request = _reference_request(match.group("body"))
        if request is None:
            continue
        key = (request.title, request.todo_id)
        if key not in seen:
            requests.append(request)
            seen.add(key)
    return requests


def _reference_request(body: str) -> ProjectTodoReferenceRequest | None:
    body = body.strip()
    if not body:
        return None
    id_match = PROJECT_TODO_REFERENCE_ID_RE.match(body)
    if id_match is None:
        return ProjectTodoReferenceRequest(title=body)
    title = id_match.group("title").strip()
    if not title:
        return None
    return ProjectTodoReferenceRequest(title=title, todo_id=UUID(id_match.group("todo_id")))
