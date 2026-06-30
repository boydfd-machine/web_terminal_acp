from __future__ import annotations

import sys

from app.contexts.clients.application import direct_registration as _direct_registration

sys.modules[__name__] = _direct_registration
