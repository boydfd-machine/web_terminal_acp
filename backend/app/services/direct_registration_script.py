from __future__ import annotations

import sys

from app.contexts.clients.application import direct_registration_script as _direct_registration_script

sys.modules[__name__] = _direct_registration_script
