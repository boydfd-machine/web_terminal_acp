from __future__ import annotations

import sys

from app.contexts.workspace.domain import project_summaries as _project_summaries

sys.modules[__name__] = _project_summaries
