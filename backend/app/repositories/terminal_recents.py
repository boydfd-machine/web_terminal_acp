from __future__ import annotations

import sys

from app.contexts.activity.infrastructure import terminal_recents_repository as _repository

sys.modules[__name__] = _repository
