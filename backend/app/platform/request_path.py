from __future__ import annotations

from fastapi import Request


def request_scope_path(request: Request) -> str:
    path = request.scope["path"]
    if not isinstance(path, str):
        raise TypeError("ASGI request scope path must be a string")
    return path
