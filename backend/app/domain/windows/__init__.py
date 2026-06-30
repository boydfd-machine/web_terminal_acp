from __future__ import annotations

import sys

from app.contexts.windows import domain as _domain
from app.contexts.windows.domain import clone_spec as _clone_spec
from app.contexts.windows.domain import remote_agents as _remote_agents
from app.contexts.windows.domain import runtime_client as _runtime_client

sys.modules[__name__] = _domain
sys.modules[f"{__name__}.clone_spec"] = _clone_spec
sys.modules[f"{__name__}.remote_agents"] = _remote_agents
sys.modules[f"{__name__}.runtime_client"] = _runtime_client
