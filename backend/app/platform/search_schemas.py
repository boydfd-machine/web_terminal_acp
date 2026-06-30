from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SearchResultOut(BaseModel):
    id: str
    index: str
    score: float | None
    snippet: str
    source: dict[str, Any]


class SearchOut(BaseModel):
    query: str
    results: list[SearchResultOut]
