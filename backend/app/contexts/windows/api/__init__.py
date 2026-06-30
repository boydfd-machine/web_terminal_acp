from __future__ import annotations

from importlib import import_module
from types import ModuleType

_ROUTE_MODULES = (
    "response_projection",
    "agent_record_projection",
    "agent_launch_config",
    "window_creation",
    "window_lifecycle_routes",
    "window_detail_routes",
    "window_git_runs_routes",
    "summary_job_routes",
)
_loaded = False


def _load_route_modules() -> None:
    global _loaded
    if _loaded:
        return
    for module_name in _ROUTE_MODULES:
        module = import_module(f"{__name__}.{module_name}")
        globals()[module_name] = module
        _export_module_names(module)
    _loaded = True


def _export_module_names(module: ModuleType) -> None:
    for name in getattr(module, "__all__", ()):
        if not name.startswith("__"):
            globals()[name] = getattr(module, name)


def __getattr__(name: str):
    _load_route_modules()
    if name in globals():
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    _load_route_modules()
    return sorted(globals())
