from __future__ import annotations

import sys

from app.contexts.clients.infrastructure import repository as _repository

sys.modules[__name__] = _repository
