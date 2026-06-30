from __future__ import annotations

import sys

from app.platform.plugins.artifact_plugins import deep_research_report as _deep_research_report

sys.modules[__name__] = _deep_research_report
