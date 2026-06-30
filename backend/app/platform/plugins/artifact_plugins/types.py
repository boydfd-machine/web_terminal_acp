from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TerminalArtifactRender:
    content_json: dict
    display_html: str | None
    metadata_json: dict


class TerminalArtifactPlugin(Protocol):
    artifact_kind: str
    label: str
    default_title: str

    def build_prompt(
        self,
        *,
        source_title: str,
        user_prompt: str | None = None,
        output_path: str | None = None,
    ) -> str:
        """Return the prompt sent into the cloned terminal."""

    def parse_output(self, output: str) -> dict:
        """Extract the artifact JSON from terminal output."""

    def render(self, content_json: dict) -> TerminalArtifactRender:
        """Render display content for this artifact."""
