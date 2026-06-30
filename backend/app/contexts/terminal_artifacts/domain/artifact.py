from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ARTIFACT_TERMINAL_RETENTION_METADATA_KEY = "terminal_retention_seconds"


@dataclass(frozen=True)
class TerminalArtifactDraft:
    artifact_kind: str
    title: str
    prompt: str | None
    output_language: str | None
    metadata_json: dict[str, Any] | None

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        plugin: object,
        default_retention_seconds: float,
    ) -> "TerminalArtifactDraft":
        metadata = dict(getattr(payload, "metadata_json", None) or {})
        retention_seconds = getattr(payload, "terminal_retention_seconds", None)
        if retention_seconds is None:
            retention_seconds = default_retention_seconds
        metadata[ARTIFACT_TERMINAL_RETENTION_METADATA_KEY] = retention_seconds
        return cls(
            artifact_kind=getattr(plugin, "artifact_kind"),
            title=getattr(payload, "title", None) or getattr(plugin, "default_title"),
            prompt=getattr(payload, "prompt", None),
            output_language=getattr(payload, "output_language", None),
            metadata_json=metadata,
        )
