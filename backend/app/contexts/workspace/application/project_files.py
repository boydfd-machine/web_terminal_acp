from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath


class ProjectPathError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectResolvedPath:
    project_path: str
    browse_root: str
    relative_path: str
    absolute_path: str


def normalize_project_path(project_path: str) -> str:
    value = project_path.strip()
    if not value.startswith("/"):
        raise ProjectPathError("project_path must be absolute")
    normalized = posixpath.normpath(value)
    if normalized == ".":
        raise ProjectPathError("project_path must be absolute")
    return normalized


def resolve_project_relative_path(
    project_path: str,
    relative_path: str | None = None,
    *,
    browse_root: str | None = None,
) -> ProjectResolvedPath:
    project_root = normalize_project_path(project_path)
    effective_root = normalize_project_path(browse_root) if browse_root is not None else project_root
    raw_relative = (relative_path or "").strip()
    if raw_relative.startswith("/"):
        raise ProjectPathError("path must be relative to project")
    normalized_relative = posixpath.normpath(raw_relative)
    if normalized_relative in {"", "."}:
        normalized_relative = "."
        absolute_path = effective_root
    elif normalized_relative == ".." or normalized_relative.startswith("../"):
        raise ProjectPathError("path escapes project")
    else:
        absolute_path = posixpath.normpath(posixpath.join(effective_root, normalized_relative))
        if absolute_path != effective_root and not absolute_path.startswith(f"{effective_root}/"):
            raise ProjectPathError("path escapes project")

    return ProjectResolvedPath(
        project_path=project_root,
        browse_root=effective_root,
        relative_path=normalized_relative,
        absolute_path=absolute_path,
    )


def relative_path_from_project(project_path: str, absolute_path: str) -> str:
    project_root = normalize_project_path(project_path)
    absolute = posixpath.normpath(absolute_path)
    if absolute == project_root:
        return "."
    prefix = f"{project_root}/"
    if not absolute.startswith(prefix):
        raise ProjectPathError("path escapes project")
    return str(PurePosixPath(absolute[len(prefix):]))
