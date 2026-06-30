from __future__ import annotations

import sys

from app.contexts.clients.infrastructure import bootstrap_installer as _bootstrap_installer

sys.modules[__name__] = _bootstrap_installer
