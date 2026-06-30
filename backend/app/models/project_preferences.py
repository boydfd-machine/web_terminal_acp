from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.model_base import Base


class ProjectAgentPreference(Base):
    __tablename__ = "project_agent_preferences"
    __table_args__ = (
        UniqueConstraint("client_id", "project_path", name="uq_project_agent_preferences_client_path"),
        Index("ix_project_agent_preferences_client_project", "client_id", "project_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    agent_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_client: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_command: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    agent_model_selection_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
