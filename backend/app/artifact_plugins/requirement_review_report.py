from __future__ import annotations

import sys

from app.platform.plugins.artifact_plugins import requirement_review_report as _requirement_review_report

sys.modules[__name__] = _requirement_review_report
