from __future__ import annotations

import sys

from app.contexts.workspace.infrastructure import summary_jobs_repository as _summary_jobs_repository

sys.modules[__name__] = _summary_jobs_repository
