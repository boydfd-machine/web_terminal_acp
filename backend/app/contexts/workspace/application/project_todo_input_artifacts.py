from __future__ import annotations

MAX_PROJECT_TODO_INPUT_ARTIFACT_IDS = 50
MAX_PROJECT_TODO_INPUT_ARTIFACT_ID_LENGTH = 128


def normalize_project_todo_input_artifact_ids(input_artifact_ids: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_id in input_artifact_ids or []:
        artifact_id = raw_id.strip()
        if not artifact_id:
            continue
        if len(artifact_id) > MAX_PROJECT_TODO_INPUT_ARTIFACT_ID_LENGTH:
            raise ValueError("input artifact id is too long")
        key = artifact_id.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(artifact_id)
        if len(normalized) > MAX_PROJECT_TODO_INPUT_ARTIFACT_IDS:
            raise ValueError("too many input artifact ids")
    return normalized
