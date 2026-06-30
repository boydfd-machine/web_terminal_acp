from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class AuthIdentity:
    user_id: str
    username: str | None = None
    email: str | None = None
    display_name: str | None = None
    auth_provider: str = "local"


_CURRENT_AUTH_IDENTITY: ContextVar[AuthIdentity | None] = ContextVar(
    "web_terminal_current_auth_identity",
    default=None,
)


def current_auth_identity() -> AuthIdentity | None:
    return _CURRENT_AUTH_IDENTITY.get()


def set_current_auth_identity(identity: AuthIdentity | None) -> Token[AuthIdentity | None]:
    return _CURRENT_AUTH_IDENTITY.set(identity)


def reset_current_auth_identity(token: Token[AuthIdentity | None]) -> None:
    _CURRENT_AUTH_IDENTITY.reset(token)


@contextmanager
def auth_identity_context(identity: AuthIdentity | None) -> Iterator[None]:
    token = set_current_auth_identity(identity)
    try:
        yield
    finally:
        reset_current_auth_identity(token)
