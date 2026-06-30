from __future__ import annotations

from uuid import UUID

MAX_MCP_DISPATCH_DEPTH = 3


class McpDispatchDepthExceeded(ValueError):
    pass


def dispatch_depth(derived_context: object) -> int:
    context = derived_context if isinstance(derived_context, dict) else {}
    depth = context.get("dispatch_depth")
    return depth if isinstance(depth, int) and depth >= 0 else 0


def next_dispatch_context(
    *,
    source_client_id: UUID,
    source_window_id: UUID,
    source_derived_context: object,
    max_depth: int = MAX_MCP_DISPATCH_DEPTH,
) -> dict[str, object]:
    depth = dispatch_depth(source_derived_context) + 1
    if depth > max_depth:
        raise McpDispatchDepthExceeded("mcp dispatch depth exceeded")
    return {
        "source_client_id": str(source_client_id),
        "source_window_id": str(source_window_id),
        "dispatch_depth": depth,
    }
