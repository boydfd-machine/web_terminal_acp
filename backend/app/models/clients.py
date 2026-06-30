from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model_base import Base
from app.models.common import (
    ClientRegistrationKeyStatus,
    ClientRuntime,
    ClientStatus,
    LOCAL_CLIENT_ID,
    WindowStatus,
    enum_values,
)

class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("name", name="uq_clients_name"),
        Index("ix_clients_status", "status"),
        Index("ix_clients_runtime", "runtime"),
        Index("ix_clients_owner_user_id", "owner_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ClientStatus] = mapped_column(
        SAEnum(
            ClientStatus,
            name="clientstatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ClientStatus.OFFLINE,
        server_default=ClientStatus.OFFLINE.value,
    )
    token_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    install_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_update_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    runtime: Mapped[ClientRuntime] = mapped_column(
        SAEnum(
            ClientRuntime,
            name="clientruntime",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ClientRuntime.remote,
        server_default=ClientRuntime.remote.value,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User | None] = relationship("User", back_populates="clients")
    folders: Mapped[list[Folder]] = relationship("Folder", back_populates="client")
    windows: Mapped[list[VirtualWindow]] = relationship("VirtualWindow", back_populates="client")
    ai_sessions: Mapped[list[AiSession]] = relationship("AiSession", back_populates="client")
    events: Mapped[list[Event]] = relationship("Event", back_populates="client")
    folder_split_jobs: Mapped[list[FolderSplitJob]] = relationship(
        "FolderSplitJob", back_populates="client"
    )


class ClientRegistrationKey(Base):
    __tablename__ = "client_registration_keys"
    __table_args__ = (
        Index("ix_client_registration_keys_status", "status"),
        Index("ix_client_registration_keys_key_hash", "key_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    status: Mapped[ClientRegistrationKeyStatus] = mapped_column(
        SAEnum(
            ClientRegistrationKeyStatus,
            name="clientregistrationkeystatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ClientRegistrationKeyStatus.active,
        server_default=ClientRegistrationKeyStatus.active.value,
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    used_client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (
        UniqueConstraint("client_id", "parent_id", "name", name="uq_folders_client_id_parent_id_name"),
        UniqueConstraint("client_id", "path", name="uq_folders_client_id_path"),
        Index("ix_folders_client_id", "client_id"),
        Index("ix_folders_parent_id", "parent_id"),
        Index("ix_folders_client_sort_name", "client_id", "sort_order", "name", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        default=lambda: LOCAL_CLIENT_ID,
        server_default=LOCAL_CLIENT_ID.hex,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship("Client", back_populates="folders")
    parent: Mapped[Folder | None] = relationship(
        "Folder", back_populates="children", remote_side=[id]
    )
    children: Mapped[list[Folder]] = relationship("Folder", back_populates="parent")
    windows: Mapped[list[VirtualWindow]] = relationship("VirtualWindow", back_populates="folder")
    split_jobs: Mapped[list[FolderSplitJob]] = relationship(
        "FolderSplitJob", back_populates="folder"
    )
