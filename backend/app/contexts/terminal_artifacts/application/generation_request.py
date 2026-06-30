from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TerminalArtifactGenerationRequest:
    client_id: UUID
    window_id: UUID
    artifact_id: UUID
    prompt: str | None = None
    output_language: str | None = None
