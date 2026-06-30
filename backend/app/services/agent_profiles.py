from __future__ import annotations

import sys

from app.contexts.agent_profiles.infrastructure import profile_store as _profile_store

sys.modules[__name__] = _profile_store
