from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class RuntimeClientKind(Enum):
    local = "local"
    remote = "remote"


@dataclass(frozen=True)
class RuntimeClient:
    id: UUID
    runtime: RuntimeClientKind

    def __post_init__(self) -> None:
        if isinstance(self.runtime, RuntimeClientKind):
            return
        object.__setattr__(
            self,
            "runtime",
            RuntimeClientKind(getattr(self.runtime, "value", self.runtime)),
        )

    @classmethod
    def from_values(cls, *, client_id: UUID, runtime: object) -> "RuntimeClient":
        return cls(id=client_id, runtime=RuntimeClientKind(getattr(runtime, "value", runtime)))
