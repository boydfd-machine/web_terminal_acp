from __future__ import annotations

import sys

from app.platform.plugins.artifact_plugins import registry as _registry

sys.modules[__name__] = _registry
