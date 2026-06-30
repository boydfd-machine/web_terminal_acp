from __future__ import annotations

import sys

from app.platform import ui_settings_repository as _ui_settings_repository

sys.modules[__name__] = _ui_settings_repository
