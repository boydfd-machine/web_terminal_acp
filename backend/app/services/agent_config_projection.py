from __future__ import annotations

import sys

from app.contexts.agent_profiles.application import config_projection as _config_projection

sys.modules[__name__] = _config_projection
