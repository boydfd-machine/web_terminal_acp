from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints


class CustomQuickKeyOut(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    input: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    shortcut: dict[str, Any] | None = None


class CustomQuickKeysOut(BaseModel):
    quick_keys: list[CustomQuickKeyOut] = Field(default_factory=list, max_length=100)


class CustomQuickKeysPutIn(BaseModel):
    quick_keys: list[CustomQuickKeyOut] = Field(default_factory=list, max_length=100)


class AppPreferencesBase(BaseModel):
    app_locale: Literal["zh-CN", "en-US"] = "zh-CN"
    summary_output_language: Literal["中文", "English"] = "中文"
    terminal_grouping_mode: Literal["project-topic", "topic", "time-topic", "project-time-topic"] = (
        "project-topic"
    )
    terminal_time_range: Literal["1d", "3d", "5d", "7d", "14d", "30d", "all"] = "7d"
    artifact_terminal_retention_seconds: int = Field(default=600, ge=0, le=3600)
    theme_skin: Literal["default", "linear", "notion", "vercel", "stripe", "raycast"] = "default"
    desktop_notifications_enabled: bool = False
    agent_command_settings: dict[str, str] = Field(default_factory=dict)
    agent_model_selection_settings: dict[str, dict[str, Any] | None] = Field(default_factory=dict)
    artifact_model_selection_settings: dict[str, dict[str, Any] | None] = Field(default_factory=dict)
    keyboard_shortcut_bindings: dict[str, dict[str, Any] | None] = Field(default_factory=dict)


class AppPreferencesOut(AppPreferencesBase):
    configured: bool = False


class AppPreferencesPutIn(AppPreferencesBase):
    pass
