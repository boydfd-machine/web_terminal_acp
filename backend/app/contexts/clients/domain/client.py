from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BearerToken:
    value: str

    @classmethod
    def parse(cls, authorization: str | None) -> "BearerToken | None":
        if authorization is None:
            return None
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            return None
        return cls(token)


@dataclass(frozen=True)
class ClientPatch:
    name: str | None


@dataclass(frozen=True)
class ClientUpdateCompletion:
    job_id: str | None
    completed_at: datetime

    @classmethod
    def now(cls, *, job_id: str | None) -> "ClientUpdateCompletion":
        return cls(
            job_id=job_id,
            completed_at=datetime.now(timezone.utc),
        )

    def response_payload(self, *, client_id: object) -> dict[str, object]:
        return {
            "client_id": client_id,
            "job_id": self.job_id,
            "completed_at": self.completed_at,
        }
