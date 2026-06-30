from __future__ import annotations

import sys
from importlib import import_module

from app.contexts.agent_profiles.infrastructure import agent_config_store as _agent_config_store

_config_service = import_module(
    "app.contexts.agent_profiles.infrastructure.agent_config_store.config_service"
)
_config_items = import_module(
    "app.contexts.agent_profiles.infrastructure.agent_config_store.config_items"
)

sys.modules[__name__] = _agent_config_store
sys.modules[f"{__name__}.config_service"] = _config_service
sys.modules[f"{__name__}.config_items"] = _config_items
