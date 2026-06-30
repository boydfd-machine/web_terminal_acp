from __future__ import annotations

import sys

from app.contexts.windows import api as _api
from app.contexts.windows.api import agent_launch_config as _agent_launch_config
from app.contexts.windows.api import agent_record_projection as _agent_record_projection
from app.contexts.windows.api import response_projection as _response_projection
from app.contexts.windows.api import summary_job_routes as _summary_job_routes
from app.contexts.windows.api import window_creation as _window_creation
from app.contexts.windows.api import window_detail_routes as _window_detail_routes
from app.contexts.windows.api import window_git_runs_routes as _window_git_runs_routes
from app.contexts.windows.api import window_lifecycle_routes as _window_lifecycle_routes

sys.modules[__name__] = _api
sys.modules[f"{__name__}.agent_launch_config"] = _agent_launch_config
sys.modules[f"{__name__}.agent_record_projection"] = _agent_record_projection
sys.modules[f"{__name__}.response_projection"] = _response_projection
sys.modules[f"{__name__}.summary_job_routes"] = _summary_job_routes
sys.modules[f"{__name__}.window_creation"] = _window_creation
sys.modules[f"{__name__}.window_detail_routes"] = _window_detail_routes
sys.modules[f"{__name__}.window_git_runs_routes"] = _window_git_runs_routes
sys.modules[f"{__name__}.window_lifecycle_routes"] = _window_lifecycle_routes
