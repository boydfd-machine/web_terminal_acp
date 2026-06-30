from __future__ import annotations

import sys

from app.contexts.windows import application as _application
from app.contexts.windows.application import errors as _errors
from app.contexts.windows.application import folder_assignment as _folder_assignment
from app.contexts.windows.application import launch_plans as _launch_plans
from app.contexts.windows.application import local_runtime_start as _local_runtime_start
from app.contexts.windows.application import remote_runtime_start as _remote_runtime_start
from app.contexts.windows.application import results as _results
from app.contexts.windows.application import runtime_capabilities as _runtime_capabilities
from app.contexts.windows.application import window_cloning as _window_cloning
from app.contexts.windows.application import window_creation as _window_creation
from app.contexts.windows.application import window_deletion as _window_deletion

sys.modules[__name__] = _application
sys.modules[f"{__name__}.errors"] = _errors
sys.modules[f"{__name__}.folder_assignment"] = _folder_assignment
sys.modules[f"{__name__}.launch_plans"] = _launch_plans
sys.modules[f"{__name__}.local_runtime_start"] = _local_runtime_start
sys.modules[f"{__name__}.remote_runtime_start"] = _remote_runtime_start
sys.modules[f"{__name__}.results"] = _results
sys.modules[f"{__name__}.runtime_capabilities"] = _runtime_capabilities
sys.modules[f"{__name__}.window_cloning"] = _window_cloning
sys.modules[f"{__name__}.window_creation"] = _window_creation
sys.modules[f"{__name__}.window_deletion"] = _window_deletion
