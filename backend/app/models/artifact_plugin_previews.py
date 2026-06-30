from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model_base import Base
from app.models.common import ArtifactPluginPreviewStatus, enum_values

if TYPE_CHECKING:
    from app.models.clients import Client
    from app.models.windows import VirtualWindow


class ArtifactPluginPreviewSession(Base):
    __tablename__ = "artifact_plugin_preview_sessions"
    __table_args__ = (
        Index("ix_artifact_plugin_previews_client_window_updated", "client_id", "window_id", "updated_at", "id"),
        Index("ix_artifact_plugin_previews_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    created_by_window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ArtifactPluginPreviewStatus] = mapped_column(
        SAEnum(
            ArtifactPluginPreviewStatus,
            name="artifactpluginpreviewstatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ArtifactPluginPreviewStatus.valid,
        server_default=ArtifactPluginPreviewStatus.valid.value,
    )
    draft_artifact_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    components_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    demo_content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    rendered_content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    display_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    client: Mapped[Client] = relationship("Client")
    window: Mapped[VirtualWindow] = relationship("VirtualWindow", foreign_keys=[window_id])
    created_by_window: Mapped[VirtualWindow] = relationship(
        "VirtualWindow",
        foreign_keys=[created_by_window_id],
    )
