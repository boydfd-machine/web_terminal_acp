from __future__ import annotations

from dataclasses import dataclass

from app.models import VirtualWindow


@dataclass(frozen=True)
class WindowMutationResult:
    window: VirtualWindow
    runtime_tags: list[str]
