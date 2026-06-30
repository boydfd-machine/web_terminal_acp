from __future__ import annotations

import sys

from app.contexts.windows.application import folder_assignment as _folder_assignment

sys.modules[__name__] = _folder_assignment
