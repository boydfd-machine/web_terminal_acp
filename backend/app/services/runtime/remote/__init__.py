from __future__ import annotations

import sys

from app.contexts.terminal_runtime.infrastructure import remote as _remote
from app.contexts.terminal_runtime.infrastructure.remote import agent_ops as _agent_ops
from app.contexts.terminal_runtime.infrastructure.remote import file_ops as _file_ops
from app.contexts.terminal_runtime.infrastructure.remote import helpers as _helpers
from app.contexts.terminal_runtime.infrastructure.remote import terminal_ops as _terminal_ops

sys.modules[__name__] = _remote
sys.modules[f"{__name__}.agent_ops"] = _agent_ops
sys.modules[f"{__name__}.file_ops"] = _file_ops
sys.modules[f"{__name__}.helpers"] = _helpers
sys.modules[f"{__name__}.terminal_ops"] = _terminal_ops
