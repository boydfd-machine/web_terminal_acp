from __future__ import annotations

import sys

from app.contexts.agent_profiles.domain import profile_update as _profile_update

sys.modules[__name__] = _profile_update
