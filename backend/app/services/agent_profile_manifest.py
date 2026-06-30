from __future__ import annotations

import sys

from app.contexts.agent_profiles.application import manifest_service as _manifest_service

sys.modules[__name__] = _manifest_service
