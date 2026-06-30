from __future__ import annotations

from app.contexts.agent_profiles.infrastructure.builtin_developer_profile_texts import (
    BACKEND_DEVELOPMENT_SKILL_MD,
    DEVELOPER_AGENT_MD,
    FRONTEND_DEVELOPMENT_SKILL_MD,
)
from app.contexts.agent_profiles.infrastructure.builtin_profile_texts import (
    DEEP_RESEARCH_SKILL_MD,
    TDD_SKILL_MD,
)

BUILTIN_DEVELOPER_PROFILE_ID = "builtin/developer"

BuiltinProfileSpec = tuple[str, str, str, tuple[tuple[str, str], ...]]

BUILTIN_PROFILE_SPECS: dict[str, BuiltinProfileSpec] = {
    BUILTIN_DEVELOPER_PROFILE_ID: (
        "Developer",
        "Built-in full-stack development agent for Web Terminal ACP frontend and backend work.",
        DEVELOPER_AGENT_MD,
        (
            ("frontend-development", FRONTEND_DEVELOPMENT_SKILL_MD),
            ("backend-development", BACKEND_DEVELOPMENT_SKILL_MD),
            ("tdd", TDD_SKILL_MD),
            ("deep-research", DEEP_RESEARCH_SKILL_MD),
        ),
    ),
}
