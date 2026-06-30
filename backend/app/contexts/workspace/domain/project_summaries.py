from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectSummaryRequest:
    project_path: str
    output_language: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> "ProjectSummaryRequest":
        project_path = getattr(payload, "project_path").strip()
        if not project_path.startswith("/"):
            raise ValueError("project_path must be absolute")
        return cls(
            project_path=project_path,
            output_language=getattr(payload, "output_language", None),
        )
