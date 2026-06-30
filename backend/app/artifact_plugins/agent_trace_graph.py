from __future__ import annotations

import sys

from app.platform.plugins.artifact_plugins import agent_trace_graph as _agent_trace_graph

sys.modules[__name__] = _agent_trace_graph
