from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints


ProjectTodoAttachmentFilename = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ProjectTodoAttachmentContentType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ProjectTodoAttachmentCreateIn(BaseModel):
    filename: ProjectTodoAttachmentFilename
    content_type: ProjectTodoAttachmentContentType
    size_bytes: int | None = Field(default=None, ge=1)


class ProjectTodoAttachmentOut(BaseModel):
    id: UUID
    todo_id: UUID
    filename: str
    content_type: str
    size_bytes: int | None
    status: str
    uploaded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectTodoAttachmentUploadOut(BaseModel):
    attachment: ProjectTodoAttachmentOut
    upload_url: str
    upload_headers: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime


class ProjectTodoAttachmentDownloadOut(BaseModel):
    attachment: ProjectTodoAttachmentOut
    download_url: str
    expires_at: datetime
