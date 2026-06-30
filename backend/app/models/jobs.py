from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, false, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model_base import Base
from app.models.common import (
    FolderSplitJobStatus,
    ProjectSummaryStatus,
    SummaryJobStatus,
    TerminalArtifactStatus,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.clients import Client, Folder
    from app.models.windows import VirtualWindow


class SummaryJob(Base):
    __tablename__ = "summary_jobs"
    __table_args__ = (
        Index("ix_summary_jobs_virtual_window_id", "virtual_window_id"),
        Index("ix_summary_jobs_status_run_after", "status", "run_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    virtual_window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SummaryJobStatus] = mapped_column(
        SAEnum(
            SummaryJobStatus,
            name="summaryjobstatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=SummaryJobStatus.pending,
        server_default=SummaryJobStatus.pending.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    allow_title_folder_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    input_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    virtual_window: Mapped[VirtualWindow] = relationship(
        "VirtualWindow", back_populates="summary_jobs"
    )


class TerminalArtifact(Base):
    __tablename__ = "terminal_artifacts"
    __table_args__ = (
        CheckConstraint("artifact_scope IN ('terminal', 'project')", name="ck_terminal_artifacts_scope"),
        Index("ix_terminal_artifacts_client_window_created", "client_id", "virtual_window_id", "created_at", "id"),
        Index("ix_terminal_artifacts_client_window_kind_created", "client_id", "virtual_window_id", "artifact_kind", "created_at", "id"),
        Index("ix_terminal_artifacts_client_scope_project_created", "client_id", "artifact_scope", "project_path", "created_at", "id"),
        Index("ix_terminal_artifacts_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    virtual_window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    source_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    ephemeral_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    artifact_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="terminal", server_default="terminal")
    project_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TerminalArtifactStatus] = mapped_column(
        SAEnum(
            TerminalArtifactStatus,
            name="terminalartifactstatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=TerminalArtifactStatus.pending,
        server_default=TerminalArtifactStatus.pending.value,
    )
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    display_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship("Client")
    virtual_window: Mapped[VirtualWindow] = relationship(
        "VirtualWindow", back_populates="artifacts", foreign_keys=[virtual_window_id]
    )
    source_window: Mapped[VirtualWindow | None] = relationship(
        "VirtualWindow", foreign_keys=[source_window_id]
    )
    ephemeral_window: Mapped[VirtualWindow | None] = relationship(
        "VirtualWindow", foreign_keys=[ephemeral_window_id]
    )


Index(
    "uq_summary_jobs_active_virtual_window_id",
    SummaryJob.virtual_window_id,
    unique=True,
    sqlite_where=SummaryJob.status == SummaryJobStatus.pending,
    postgresql_where=SummaryJob.status == SummaryJobStatus.pending,
)


class FolderSplitJob(Base):
    __tablename__ = "folder_split_jobs"
    __table_args__ = (
        Index("ix_folder_split_jobs_client_id", "client_id"),
        Index("ix_folder_split_jobs_folder_id", "folder_id"),
        Index("ix_folder_split_jobs_status_run_after", "status", "run_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[FolderSplitJobStatus] = mapped_column(
        SAEnum(
            FolderSplitJobStatus,
            name="foldersplitjobstatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=FolderSplitJobStatus.pending,
        server_default=FolderSplitJobStatus.pending.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship("Client", back_populates="folder_split_jobs")
    folder: Mapped[Folder] = relationship("Folder", back_populates="split_jobs")


class ProjectSummary(Base):
    __tablename__ = "project_summaries"
    __table_args__ = (
        UniqueConstraint("client_id", "project_path", name="uq_project_summaries_client_path"),
        Index("ix_project_summaries_client_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ProjectSummaryStatus] = mapped_column(
        SAEnum(
            ProjectSummaryStatus,
            name="projectsummarystatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ProjectSummaryStatus.succeeded,
        server_default=ProjectSummaryStatus.succeeded.value,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectReviewConfig(Base):
    __tablename__ = "project_review_configs"
    __table_args__ = (
        UniqueConstraint("client_id", "project_path", name="uq_project_review_configs_client_path"),
        Index("ix_project_review_configs_client_project", "client_id", "project_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    pr_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="LOCAL_CARD", server_default="LOCAL_CARD"
    )
    pr_provider_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    review_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_agent_command: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    review_agent_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    auto_create_review_target: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    auto_dispatch_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    merge_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL", server_default="MANUAL")
    required_artifact_kinds_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class UiSetting(Base):
    __tablename__ = "ui_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TerminalRecentUsage(Base):
    __tablename__ = "terminal_recent_usages"
    __table_args__ = (
        UniqueConstraint("client_id", "window_id", name="uq_terminal_recent_usages_client_window"),
        Index("ix_terminal_recent_usages_client_last_used", "client_id", "last_used_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("virtual_windows.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TerminalNotificationState(Base):
    __tablename__ = "terminal_notification_states"
    __table_args__ = (
        UniqueConstraint("client_id", "window_id", name="uq_terminal_notification_states_client_window"),
        Index("ix_terminal_notification_states_client_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WindowGitBinding(Base):
    __tablename__ = "window_git_bindings"
    __table_args__ = (
        UniqueConstraint("virtual_window_id", name="uq_window_git_bindings_virtual_window_id"),
        Index("ix_window_git_bindings_client_id", "client_id"),
        Index("ix_window_git_bindings_window_client", "virtual_window_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    virtual_window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    main_repo_root: Mapped[str] = mapped_column(Text, nullable=False)
    worktree_root: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_method: Mapped[str] = mapped_column(String(32), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GitWorktreeRun(Base):
    __tablename__ = "git_worktree_runs"
    __table_args__ = (
        UniqueConstraint(
            "virtual_window_id",
            "command_sequence",
            name="uq_git_worktree_runs_window_sequence",
        ),
        Index("ix_git_worktree_runs_client_window_started", "client_id", "virtual_window_id", "started_at"),
        Index("ix_git_worktree_runs_window_pending", "virtual_window_id", "pending_commit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    virtual_window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="CASCADE"), nullable=False
    )
    command_sequence: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    main_repo_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    worktree_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    end_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    session_diff_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pending_commit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "uq_folder_split_jobs_active_folder_id",
    FolderSplitJob.folder_id,
    unique=True,
    sqlite_where=FolderSplitJob.status.in_(
        [
            FolderSplitJobStatus.pending,
            FolderSplitJobStatus.running,
        ]
    ),
    postgresql_where=FolderSplitJob.status.in_(
        [
            FolderSplitJobStatus.pending,
            FolderSplitJobStatus.running,
        ]
    ),
)
