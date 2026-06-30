from __future__ import annotations

import sys

from app.contexts.activity.infrastructure import ai_sessions_repository as _repository

sys.modules[__name__] = _repository
