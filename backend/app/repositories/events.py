from __future__ import annotations

import sys

from app.contexts.activity.infrastructure import events_repository as _repository

sys.modules[__name__] = _repository
