from __future__ import annotations

import sys

from app.platform.plugins.artifact_plugins import review_agent_artifacts as _review_agent_artifacts

sys.modules[__name__] = _review_agent_artifacts
