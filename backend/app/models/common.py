from __future__ import annotations

import uuid
from enum import Enum

LOCAL_CLIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class ClientStatus(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class ClientRuntime(Enum):
    local = "local"
    remote = "remote"


class ClientRegistrationKeyStatus(Enum):
    active = "ACTIVE"
    used = "USED"


class WindowStatus(Enum):
    active = "ACTIVE"
    archived = "ARCHIVED"
    error = "ERROR"
    disconnected = "DISCONNECTED"


class EventSourceType(Enum):
    terminal = "terminal"
    claude_jsonl = "claude_jsonl"
    codex_trace = "codex_trace"
    summary = "summary"
    agent_tool_record = "agent_tool_record"


class SummaryJobStatus(Enum):
    pending = "PENDING"
    running = "RUNNING"
    succeeded = "SUCCEEDED"
    failed = "FAILED"


class FolderSplitJobStatus(Enum):
    pending = "PENDING"
    running = "RUNNING"
    succeeded = "SUCCEEDED"
    failed = "FAILED"


class ProjectSummaryStatus(Enum):
    pending = "PENDING"
    running = "RUNNING"
    succeeded = "SUCCEEDED"
    failed = "FAILED"


class ProjectTodoStatus(Enum):
    todo = "TODO"
    blocked = "BLOCKED"
    dispatched = "DISPATCHED"
    awaiting_review = "AWAITING_REVIEW"
    done = "DONE"


class TerminalArtifactStatus(Enum):
    pending = "PENDING"
    running = "RUNNING"
    succeeded = "SUCCEEDED"
    failed = "FAILED"


class ArtifactPluginPreviewStatus(Enum):
    valid = "valid"
    invalid = "invalid"
