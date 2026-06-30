from __future__ import annotations

import os
import re

CURSOR_OFFICIAL_MODEL_PRESET_ID = "cursor-official"

_MODEL_LINE_RE = re.compile(r"^([^\s]+)\s+-\s+(.+)$")


def cursor_project_dir_name(workspace_path: str) -> str:
    try:
        real_path = os.path.realpath(workspace_path)
    except OSError:
        real_path = workspace_path
    return real_path.lstrip("/").replace("/", "-")


def is_cursor_official_model_preset(preset_id: str | None) -> bool:
    return preset_id == CURSOR_OFFICIAL_MODEL_PRESET_ID


def parse_cursor_official_models_output(text: str) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("available models"):
            continue
        match = _MODEL_LINE_RE.match(line)
        if match is None:
            continue
        model_id, label = match.group(1), match.group(2).strip()
        if not model_id:
            continue
        models.append({"id": model_id, "label": label})
    return models
