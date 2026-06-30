from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ProjectTodoAnnotationIn(BaseModel):
    annotation: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=65536),
    ]
