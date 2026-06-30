from __future__ import annotations

from typing import Any


def default_preview_content_json(
    json_schema: dict[str, Any],
    *,
    artifact_kind: str,
    title: str,
) -> dict[str, Any]:
    value = _sample_for_schema(json_schema, field_name=None)
    if not isinstance(value, dict):
        value = {}
    if _allows_object_field(json_schema, "artifact_kind"):
        value.setdefault("artifact_kind", artifact_kind)
    if _allows_object_field(json_schema, "title"):
        value.setdefault("title", title)
    return value


def _sample_for_schema(schema: object, *, field_name: str | None) -> Any:
    if not isinstance(schema, dict):
        return _fallback_for_field(field_name)
    if "const" in schema:
        return schema["const"]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    schema_type = _schema_type(schema)
    if schema_type == "object":
        return _sample_object(schema)
    if schema_type == "array":
        return _sample_array(schema, field_name=field_name)
    if schema_type == "integer":
        return schema.get("minimum", 1)
    if schema_type == "number":
        return float(schema.get("minimum", 1))
    if schema_type == "boolean":
        return True
    if schema_type == "null":
        return None
    return _fallback_for_field(field_name)


def _schema_type(schema: dict[str, Any]) -> str:
    raw = schema.get("type")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        for candidate in ("object", "array", "string", "number", "integer", "boolean", "null"):
            if candidate in raw:
                return candidate
    if isinstance(schema.get("properties"), dict):
        return "object"
    if isinstance(schema.get("items"), dict):
        return "array"
    return "string"


def _sample_object(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    required = schema.get("required")
    required_fields = [item for item in required if isinstance(item, str)] if isinstance(required, list) else []
    fields = list(dict.fromkeys([*required_fields, "artifact_kind", "title", "summary"]))
    value: dict[str, Any] = {}
    for field in fields:
        field_schema = properties.get(field)
        if field_schema is not None:
            value[field] = _sample_for_schema(field_schema, field_name=field)
        elif field in required_fields and _allows_object_field(schema, field):
            value[field] = _fallback_for_field(field)
    return value


def _sample_array(schema: dict[str, Any], *, field_name: str | None) -> list[Any]:
    min_items = schema.get("minItems")
    count = min_items if isinstance(min_items, int) and min_items > 0 else 1
    item_schema = schema.get("items")
    item = _sample_for_schema(item_schema, field_name=_singular(field_name)) if item_schema is not None else {}
    return [item for _ in range(count)]


def _fallback_for_field(field_name: str | None) -> str:
    if field_name in {"artifact_kind", "type", "status", "priority", "severity"}:
        return "demo"
    if field_name in {"title", "name", "label", "task"}:
        return "Preview"
    if field_name in {"summary", "executive_summary", "description", "detail"}:
        return "Preview content"
    if field_name == "id":
        return "preview-1"
    return "Example"


def _singular(field_name: str | None) -> str | None:
    if field_name is None:
        return None
    return field_name[:-1] if field_name.endswith("s") and len(field_name) > 1 else field_name


def _allows_object_field(schema: dict[str, Any], field_name: str) -> bool:
    properties = schema.get("properties")
    if isinstance(properties, dict) and field_name in properties:
        return True
    return schema.get("additionalProperties") is not False
