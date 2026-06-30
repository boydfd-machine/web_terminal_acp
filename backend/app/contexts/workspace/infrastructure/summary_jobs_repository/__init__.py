from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType

from app.config import get_settings as get_settings


_MODULE_NAMES = (
    "job_status",
    "summary_context",
    "job_repository",
)

for _module_name in _MODULE_NAMES:
    _module = import_module(f"{__name__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


class _SummaryJobsRepositoryPackage(ModuleType):
    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name == "get_settings":
            sys.modules[f"{__name__}.job_status"].get_settings = value


sys.modules[__name__].__class__ = _SummaryJobsRepositoryPackage

__all__ = [name for name in globals() if not name.startswith("__")]
