from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, JSON, String, Text, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model_base import Base
from app.models.common import LOCAL_CLIENT_ID, WindowStatus, enum_values

if TYPE_CHECKING:
    from app.models.agent_events import AiSession, Event
    from app.models.clients import Client, Folder
    from app.models.jobs import SummaryJob, TerminalArtifact


class VirtualWindow(Base):
    __tablename__ = "virtual_windows"
    __table_args__ = (
        Index("ix_virtual_windows_client_id", "client_id"),
        Index("ix_virtual_windows_folder_id", "folder_id"),
        Index("ix_virtual_windows_status", "status"),
        Index("ix_virtual_windows_client_root_created", "client_id", "root_window_id", "created_at", "id"),
        Index("ix_virtual_windows_parent_window", "parent_window_id"),
        Index("ix_virtual_windows_client_folder_created", "client_id", "folder_id", "created_at", "title", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        default=lambda: LOCAL_CLIENT_ID,
        server_default=LOCAL_CLIENT_ID.hex,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    parent_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    root_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    derived_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    derived_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[WindowStatus] = mapped_column(
        SAEnum(
            WindowStatus,
            name="windowstatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=WindowStatus.active,
        server_default=WindowStatus.active.value,
    )
    tmux_session: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tmux_window_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tmux_window_index: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remote_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_window_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cwd: Mapped[str | None] = mapped_column(Text, nullable=True)
    shell_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_manually_overridden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    folder_manually_overridden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    title_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    terminal_last_output_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_presence_latest_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_latest_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_latest_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    agent_activity_latest_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_deferred_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_pending_subagent_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    agent_activity_latest_subagent_call_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_latest_user_input_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_burst_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_activity_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    manual_work_status_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    manual_work_status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[Client] = relationship("Client", back_populates="windows")
    folder: Mapped[Folder | None] = relationship("Folder", back_populates="windows")
    parent_window: Mapped[VirtualWindow | None] = relationship(
        "VirtualWindow", foreign_keys=[parent_window_id], remote_side=[id]
    )
    root_window: Mapped[VirtualWindow | None] = relationship(
        "VirtualWindow", foreign_keys=[root_window_id], remote_side=[id]
    )
    ai_sessions: Mapped[list[AiSession]] = relationship("AiSession", back_populates="virtual_window")
    events: Mapped[list[Event]] = relationship("Event", back_populates="virtual_window")
    summary_jobs: Mapped[list[SummaryJob]] = relationship(
        "SummaryJob", back_populates="virtual_window"
    )
    artifacts: Mapped[list[TerminalArtifact]] = relationship(
        "TerminalArtifact",
        back_populates="virtual_window",
        foreign_keys="TerminalArtifact.virtual_window_id",
    )
    title_history: Mapped[list[WindowTitleHistory]] = relationship(
        "WindowTitleHistory", back_populates="virtual_window"
    )


class WindowTitleHistory(Base):
    __tablename__ = "window_title_history"
    __table_args__ = (
        Index("ix_window_title_history_client_window_created", "client_id", "virtual_window_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    virtual_window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    client: Mapped[Client] = relationship("Client")
    virtual_window: Mapped[VirtualWindow] = relationship(
        "VirtualWindow", back_populates="title_history"
    )
