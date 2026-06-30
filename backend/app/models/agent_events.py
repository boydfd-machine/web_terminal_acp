from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model_base import Base
from app.models.common import EventSourceType, LOCAL_CLIENT_ID, enum_values

if TYPE_CHECKING:
    from app.models.clients import Client
    from app.models.windows import VirtualWindow


class AiSession(Base):
    __tablename__ = "ai_sessions"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "provider",
            "source_id",
            "virtual_window_id",
            name="uq_ai_sessions_client_provider_source_window",
        ),
        Index("ix_ai_sessions_client_id", "client_id"),
        Index("ix_ai_sessions_virtual_window_id", "virtual_window_id"),
        Index("ix_ai_sessions_client_window_updated", "client_id", "virtual_window_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        default=lambda: LOCAL_CLIENT_ID,
        server_default=LOCAL_CLIENT_ID.hex,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    virtual_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship("Client", back_populates="ai_sessions")
    virtual_window: Mapped[VirtualWindow | None] = relationship(
        "VirtualWindow", back_populates="ai_sessions"
    )
    events: Mapped[list[Event]] = relationship("Event", back_populates="ai_session")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("client_id", "fingerprint", name="uq_events_client_id_fingerprint"),
        Index("ix_events_client_id", "client_id"),
        Index("ix_events_virtual_window_id", "virtual_window_id"),
        Index("ix_events_ai_session_id", "ai_session_id"),
        Index("ix_events_source_type_source_id", "source_type", "source_id"),
        Index("ix_events_agent_record_window", "client_id", "virtual_window_id", "created_at", "id"),
        Index("ix_events_client_window_kind_created_id", "client_id", "virtual_window_id", "kind", "created_at", "id"),
        Index("ix_events_client_window_source_created_id", "client_id", "virtual_window_id", "source_type", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        default=lambda: LOCAL_CLIENT_ID,
        server_default=LOCAL_CLIENT_ID.hex,
    )
    source_type: Mapped[EventSourceType] = mapped_column(
        SAEnum(
            EventSourceType,
            name="eventsourcetype",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    virtual_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    ai_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_sessions.id", ondelete="SET NULL"), nullable=True
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    client: Mapped[Client] = relationship("Client", back_populates="events")
    virtual_window: Mapped[VirtualWindow | None] = relationship(
        "VirtualWindow", back_populates="events"
    )
    ai_session: Mapped[AiSession | None] = relationship("AiSession", back_populates="events")


Index(
    "ix_events_source_unindexed_created",
    Event.source_type,
    Event.created_at,
    Event.id,
    postgresql_where=Event.indexed_at.is_(None),
    sqlite_where=Event.indexed_at.is_(None),
)

Index(
    "ix_events_agent_record_non_output_window",
    Event.client_id,
    Event.virtual_window_id,
    Event.created_at,
    Event.id,
    postgresql_where=Event.kind != "terminal_output",
    sqlite_where=Event.kind != "terminal_output",
)

Index(
    "ix_events_agent_activity_window_created",
    Event.client_id,
    Event.virtual_window_id,
    Event.created_at,
    Event.id,
    postgresql_where=Event.source_type.in_(
        [
            EventSourceType.agent_tool_record,
            EventSourceType.codex_trace,
            EventSourceType.claude_jsonl,
        ]
    ),
    sqlite_where=Event.source_type.in_(
        [
            EventSourceType.agent_tool_record,
            EventSourceType.codex_trace,
            EventSourceType.claude_jsonl,
        ]
    ),
)

Index(
    "ix_events_client_agent_message_recent",
    Event.client_id,
    Event.created_at.desc(),
    Event.id.desc(),
    postgresql_where=(
        (Event.kind.in_(["user_message", "assistant_message"]))
        | (
            (Event.kind == "system_message")
            & (Event.source_type == EventSourceType.agent_tool_record)
        )
        | (Event.kind.in_(["response_item", "event_msg"]))
    ),
    sqlite_where=(
        (Event.kind.in_(["user_message", "assistant_message"]))
        | (
            (Event.kind == "system_message")
            & (Event.source_type == EventSourceType.agent_tool_record)
        )
        | (Event.kind.in_(["response_item", "event_msg"]))
    ),
)

Index(
    "ix_events_terminal_input_window_created",
    Event.client_id,
    Event.virtual_window_id,
    Event.created_at,
    Event.id,
    postgresql_where=Event.kind == "terminal_input_command",
    sqlite_where=Event.kind == "terminal_input_command",
)

Index(
    "ix_events_terminal_finished_window_created",
    Event.client_id,
    Event.virtual_window_id,
    Event.created_at,
    Event.id,
    postgresql_where=Event.kind == "terminal_command_finished",
    sqlite_where=Event.kind == "terminal_command_finished",
)
