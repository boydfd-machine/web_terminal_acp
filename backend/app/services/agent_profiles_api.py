from __future__ import annotations

import sys

from app.contexts.agent_profiles.application import api_service as _api_service

sys.modules[__name__] = _api_service
