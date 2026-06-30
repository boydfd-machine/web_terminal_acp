from __future__ import annotations

import sys

from app.contexts.clients.infrastructure import bootstrap_ssh as _bootstrap_ssh

sys.modules[__name__] = _bootstrap_ssh
