from __future__ import annotations

import sys

from app.platform.plugins import artifact_plugins as _artifact_plugins
from app.platform.plugins.artifact_plugins import agent_pitfalls as _agent_pitfalls
from app.platform.plugins.artifact_plugins import agent_trace_graph as _agent_trace_graph
from app.platform.plugins.artifact_plugins import deep_research_report as _deep_research_report
from app.platform.plugins.artifact_plugins import requirement_review_report as _requirement_review_report
from app.platform.plugins.artifact_plugins import registry as _registry
from app.platform.plugins.artifact_plugins import review_agent_artifacts as _review_agent_artifacts
from app.platform.plugins.artifact_plugins import types as _types

sys.modules[__name__] = _artifact_plugins
sys.modules[f"{__name__}.agent_pitfalls"] = _agent_pitfalls
sys.modules[f"{__name__}.agent_trace_graph"] = _agent_trace_graph
sys.modules[f"{__name__}.deep_research_report"] = _deep_research_report
sys.modules[f"{__name__}.requirement_review_report"] = _requirement_review_report
sys.modules[f"{__name__}.registry"] = _registry
sys.modules[f"{__name__}.review_agent_artifacts"] = _review_agent_artifacts
sys.modules[f"{__name__}.types"] = _types
