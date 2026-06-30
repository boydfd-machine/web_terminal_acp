from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import subscriber_writer as _subscriber_writer

sys.modules[__name__] = _subscriber_writer
