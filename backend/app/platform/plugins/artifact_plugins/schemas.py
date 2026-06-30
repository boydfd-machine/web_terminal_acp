from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

ArtifactPluginDomain = Literal["terminal", "project"]
ArtifactPluginOrigin = Literal["built_in", "managed"]
ArtifactPluginFormat = Literal["legacy_python", "template"]
ArtifactPluginPreviewStatus = Literal["valid", "invalid"]
ArtifactPluginKind = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
ArtifactPluginSource = Annotated[str, StringConstraints(min_length=1, max_length=262144)]
ArtifactPluginTemplate = Annotated[str, StringConstraints(min_length=1, max_length=262144)]
ArtifactPluginPreviewTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ArtifactPluginDescriptorOut(BaseModel):
    domain: ArtifactPluginDomain
    artifact_kind: ArtifactPluginKind
    label: str
    default_title: str
    origin: ArtifactPluginOrigin
    editable: bool
    plugin_format: ArtifactPluginFormat
    downloadable: bool = True
    path: str | None = None
    validation_error: str | None = None


class ArtifactPluginListOut(BaseModel):
    plugins: list[ArtifactPluginDescriptorOut] = Field(default_factory=list)


class ArtifactPluginSourceOut(ArtifactPluginDescriptorOut):
    source: str | None = None
    python_source: str | None = None
    prompt_template: str | None = None
    html_template: str | None = None
    json_schema: dict[str, Any] | None = None
    preview_content_json: dict[str, Any] | None = None
    preview_content_json_by_locale: dict[str, dict[str, Any]] | None = None


class ArtifactPluginPutIn(BaseModel):
    source: ArtifactPluginSource | None = None
    python_source: ArtifactPluginSource | None = None
    prompt_template: ArtifactPluginTemplate | None = None
    html_template: ArtifactPluginTemplate | None = None
    json_schema: dict[str, Any] | None = None
    preview_content_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ArtifactPluginPutIn":
        has_legacy_source = self.source is not None
        has_components = (
            self.python_source is not None
            or self.prompt_template is not None
            or self.html_template is not None
            or self.json_schema is not None
            or self.preview_content_json is not None
        )
        if has_legacy_source and has_components:
            raise ValueError("use either legacy source or artifact plugin components")
        if has_legacy_source:
            return self
        missing = [
            name
            for name, value in (
                ("python_source", self.python_source),
                ("prompt_template", self.prompt_template),
                ("html_template", self.html_template),
                ("json_schema", self.json_schema),
            )
            if value is None
        ]
        if missing:
            raise ValueError(f"artifact plugin components missing: {', '.join(missing)}")
        return self


class ArtifactPluginPreviewUpsertIn(BaseModel):
    client_id: UUID
    window_id: UUID
    title: ArtifactPluginPreviewTitle
    python_source: ArtifactPluginSource
    prompt_template: ArtifactPluginTemplate
    html_template: ArtifactPluginTemplate
    json_schema: dict[str, Any]
    demo_content_json: dict[str, Any] | None = None


class ArtifactPluginPreviewMcpUpsertIn(BaseModel):
    preview_id: UUID | None = None
    title: ArtifactPluginPreviewTitle
    python_source: ArtifactPluginSource
    prompt_template: ArtifactPluginTemplate
    html_template: ArtifactPluginTemplate
    json_schema: dict[str, Any]
    demo_content_json: dict[str, Any] | None = None


class ArtifactPluginPreviewOut(BaseModel):
    id: UUID
    client_id: UUID
    window_id: UUID
    created_by_window_id: UUID
    status: ArtifactPluginPreviewStatus
    draft_artifact_kind: str | None
    title: str
    components_json: dict[str, Any]
    demo_content_json: dict[str, Any] | None
    rendered_content_json: dict[str, Any] | None
    display_html: str | None = None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class ArtifactPluginPreviewListOut(BaseModel):
    window_id: UUID
    previews: list[ArtifactPluginPreviewOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool
