from importlib import import_module as _import_module

# ruff: noqa: F821

for _module_name in ("config_items", "config_model_types"):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value.is_integer() and value > 0:
        return int(value)
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def _enum_choice(value: object, choices: tuple[str, ...]) -> str | None:
    text = _string(value)
    return text if text in choices else None


def _codex_reasoning_effort(value: object) -> str | None:
    return _enum_choice(value, CODEX_REASONING_EFFORTS)


def _claude_reasoning_effort(value: object) -> str | None:
    return _enum_choice(value, CLAUDE_REASONING_EFFORTS)


def _claude_routing_from_payload(value: object) -> ClaudeModelRouting | None:
    if not isinstance(value, dict):
        return None
    mode = value.get("mode")
    return ClaudeModelRouting(
        mode=mode if mode in {"all", "split"} else "all",
        model=_string(value.get("model")),
        opus_model=_string(value.get("opus_model")),
        sonnet_model=_string(value.get("sonnet_model")),
        haiku_model=_string(value.get("haiku_model")),
    )


def _claude_routing_payload(routing: ClaudeModelRouting) -> dict[str, object]:
    payload: dict[str, object] = {"mode": routing.mode}
    for key in ("model", "opus_model", "sonnet_model", "haiku_model"):
        value = getattr(routing, key)
        if value is not None:
            payload[key] = value
    return payload


__all__ = [name for name in globals() if not name.startswith("__")]
