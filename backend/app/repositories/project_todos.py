from __future__ import annotations

import sys

from app.contexts.workspace.infrastructure import project_todos_repository as _repository

sys.modules[__name__] = _repository
