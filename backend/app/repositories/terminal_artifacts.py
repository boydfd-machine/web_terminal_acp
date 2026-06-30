from __future__ import annotations

import sys

from app.contexts.terminal_artifacts.infrastructure import repository as _repository

sys.modules[__name__] = _repository
