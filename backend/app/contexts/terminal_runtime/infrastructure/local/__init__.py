from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType

_MODULE_NAMES = (
    "pty_io",
    "output_pipe",
    "runtime",
    "stale_window_cleanup",
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


class _LocalRuntimePackage(ModuleType):
    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        for module in _MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _LocalRuntimePackage

__all__ = [name for name in globals() if not name.startswith("__")]
