from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType


_MODULE_NAMES = (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_system_skill_archive",
    "config_managed_skills",
    "config_system_queries",
    "config_model_types",
    "config_model_payload",
    "config_model_presets",
    "config_model_settings",
    "config_model_materialization",
    "config_model_metadata",
    "config_system_defaults",
    "config_system_plugins",
    "config_builtin_mcp",
    "config_system_detail",
    "config_system_materialization",
    "config_system_snapshot",
)

_MODULES = tuple(import_module(f"{__name__}.{_module_name}") for _module_name in _MODULE_NAMES)

for _module in _MODULES:
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

_exports = {name: value for name, value in globals().items() if not name.startswith("__")}
for _module in _MODULES:
    _module.__dict__.update(_exports)


class _AgentConfigStoreModule(ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for module in _MODULES:
            if name in module.__dict__:
                setattr(module, name, value)


sys.modules[__name__].__class__ = _AgentConfigStoreModule

__all__ = [name for name in globals() if not name.startswith("__")]
