from __future__ import annotations

import sys

from app.contexts.clients.application import client_update as _client_update

sys.modules[__name__] = _client_update
