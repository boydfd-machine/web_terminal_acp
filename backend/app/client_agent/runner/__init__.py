from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType


_MODULE_NAMES = (
    "bulk_receive",
    "connect_options",
    "runtime_availability",
    "reconnect_policy",
    "supervisor",
    "cleanup_runtime",
    "cleanup_hooks",
    "lifecycle",
    "message_io",
    "background_jobs",
    "file_git_config_handlers",
    "runtime_message_handlers",
)

_MODULES = tuple(import_module(f"{__name__}.{module_name}") for module_name in _MODULE_NAMES)

_exports = {}
for _module in _MODULES:
    _exports.update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )
globals().update(_exports)

for _module in _MODULES:
    _module.__dict__.update(_exports)


class _RunnerPackage(ModuleType):
    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        for module in _MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _RunnerPackage

__all__ = [name for name in globals() if not name.startswith("__")]
