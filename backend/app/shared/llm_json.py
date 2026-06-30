from __future__ import annotations

import re

_JSON_MARKDOWN_FENCE_PATTERN = re.compile(
    r"\A\s*```(?:json|JSON)?\s*\n(?P<body>.*)\n```\s*\Z",
    re.DOTALL,
)


def strip_json_markdown_fence(text: str) -> str:
    match = _JSON_MARKDOWN_FENCE_PATTERN.match(text)
    if match is None:
        return text
    return match.group("body").strip()
