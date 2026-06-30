from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProjectFileSearchMatchOut(BaseModel):
    field: Literal["path", "snippet"]
    start: int
    end: int


class ProjectFileSearchResultOut(BaseModel):
    project_path: str
    path: str
    line: int | None = None
    snippet: str
    matches: list[ProjectFileSearchMatchOut] = Field(default_factory=list)


class ProjectFileSearchOut(BaseModel):
    query: str
    results: list[ProjectFileSearchResultOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool
    scanned_files: int
    truncated: bool = False
