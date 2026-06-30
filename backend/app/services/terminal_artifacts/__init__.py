from __future__ import annotations

import sys

from app.contexts.terminal_artifacts import application as _application
from app.contexts.terminal_artifacts.application import api_service as _api_service

sys.modules[__name__] = _application
sys.modules[f"{__name__}.api_service"] = _api_service
