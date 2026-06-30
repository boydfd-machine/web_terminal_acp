from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from types import ModuleType
from typing import Any, Callable

from jinja2 import Environment, StrictUndefined
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects, _single_line
from .preview_data import default_preview_content_json
from .types import TerminalArtifactRender

TemplateHook = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ArtifactPluginComponents:
    artifact_kind: str
    label: str
    default_title: str
    python_source: str
    prompt_template: str
    html_template: str
    json_schema: dict[str, Any]
    preview_content_json: dict[str, Any]
    normalize_content: TemplateHook | None = None
    metadata_json: TemplateHook | None = None
    template_context: TemplateHook | None = None


class TemplateTerminalArtifactPlugin:
    def __init__(self, components: ArtifactPluginComponents) -> None:
        self.artifact_kind = components.artifact_kind
        self.label = components.label
        self.default_title = components.default_title
        self._components = components
        try:
            Draft202012Validator.check_schema(components.json_schema)
        except SchemaError as exc:
            raise ValueError(f"artifact plugin JSON schema is invalid: {exc.message}") from exc
        self._validator = Draft202012Validator(
            components.json_schema,
            registry=_referenced_schema_registry(),
        )
        self._validate(components.preview_content_json)

    def build_prompt(
        self,
        *,
        source_title: str,
        user_prompt: str | None = None,
        output_path: str | None = None,
    ) -> str:
        rendered = _render_prompt_template(
            self._components.prompt_template,
            {
                "artifact_kind": self.artifact_kind,
                "label": self.label,
                "default_title": self.default_title,
                "source_title": source_title,
                "user_prompt": user_prompt,
                "output_path": output_path,
                "output_instruction": _output_instruction(output_path),
                "json_schema": self._components.json_schema,
                "json_schema_text": json.dumps(
                    self._components.json_schema,
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        )
        return _single_line(rendered)

    def parse_output(self, output: str) -> dict:
        last_error: str | None = None
        for candidate in (*_iter_json_objects(output), *_iter_wrapped_json_objects(output)):
            try:
                return self._validate_and_normalize(candidate)
            except ValueError as exc:
                last_error = str(exc)
        if last_error:
            raise ValueError(f"{self.artifact_kind} JSON did not match schema: {last_error}")
        raise ValueError(f"{self.artifact_kind} JSON was not found in terminal output")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        normalized = self._validate_and_normalize(content_json)
        context = self._template_context(normalized)
        html = _render_html_template(self._components.html_template, context)
        metadata_json = {"renderer": "jinja2", "artifact_kind": self.artifact_kind}
        if self._components.metadata_json is not None:
            metadata_json.update(_dict_hook(self._components.metadata_json, normalized, "metadata_json"))
        return TerminalArtifactRender(
            content_json=normalized,
            display_html=html,
            metadata_json=metadata_json,
        )

    def _validate_and_normalize(self, value: dict[str, Any]) -> dict[str, Any]:
        self._validate(value)
        normalized = value
        if self._components.normalize_content is not None:
            normalized = _dict_hook(self._components.normalize_content, value, "normalize_content")
            self._validate(normalized)
        return normalized

    def _validate(self, value: dict[str, Any]) -> None:
        try:
            self._validator.validate(value)
        except ValidationError as exc:
            path = ".".join(str(item) for item in exc.absolute_path)
            location = f" at {path}" if path else ""
            raise ValueError(f"{exc.message}{location}") from exc

    def _template_context(self, content_json: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {
            "artifact_kind": self.artifact_kind,
            "label": self.label,
            "default_title": self.default_title,
            "content": content_json,
            "content_json": content_json,
        }
        if self._components.template_context is not None:
            context.update(_dict_hook(self._components.template_context, content_json, "template_context"))
        return context


def components_from_module(
    module: ModuleType,
    *,
    python_source: str,
    prompt_template: str,
    html_template: str,
    json_schema: dict[str, Any],
    preview_content_json: dict[str, Any] | None = None,
) -> ArtifactPluginComponents:
    values = _component_values(module)
    artifact_kind = _required_text(values, "artifact_kind")
    default_title = _required_text(values, "default_title")
    return ArtifactPluginComponents(
        artifact_kind=artifact_kind,
        label=_required_text(values, "label"),
        default_title=default_title,
        python_source=python_source,
        prompt_template=prompt_template,
        html_template=html_template,
        json_schema=json_schema,
        preview_content_json=preview_content_json
        if preview_content_json is not None
        else default_preview_content_json(
            json_schema,
            artifact_kind=artifact_kind,
            title=default_title,
        ),
        normalize_content=_optional_hook(values, "normalize_content"),
        metadata_json=_optional_hook(values, "metadata_json"),
        template_context=_optional_hook(values, "template_context"),
    )


def default_html_template() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ content.title | default(default_title) }}</title>
</head>
<body>
  <main>
    <h1>{{ content.title | default(default_title) }}</h1>
    <pre>{{ content | tojson_pretty }}</pre>
  </main>
</body>
</html>"""


def _component_values(module: ModuleType) -> dict[str, Any]:
    factory = getattr(module, "create_plugin_components", None)
    raw = factory() if callable(factory) else module
    if isinstance(raw, dict):
        return raw
    return {
        "artifact_kind": getattr(raw, "artifact_kind", getattr(raw, "ARTIFACT_KIND", None)),
        "label": getattr(raw, "label", getattr(raw, "LABEL", None)),
        "default_title": getattr(raw, "default_title", getattr(raw, "DEFAULT_TITLE", None)),
        "normalize_content": getattr(module, "normalize_content", None),
        "metadata_json": getattr(module, "metadata_json", None),
        "template_context": getattr(module, "template_context", None),
    }


def _required_text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"artifact plugin {key} must be a non-empty string")
    return value.strip()


def _optional_hook(values: dict[str, Any], key: str) -> TemplateHook | None:
    value = values.get(key)
    if value is None:
        return None
    if not callable(value):
        raise ValueError(f"artifact plugin {key} must be callable")
    return value


def _dict_hook(hook: TemplateHook, content_json: dict[str, Any], name: str) -> dict[str, Any]:
    value = hook(content_json)
    if not isinstance(value, dict):
        raise ValueError(f"artifact plugin {name} must return an object")
    return value


def _render_prompt_template(template: str, context: dict[str, Any]) -> str:
    env = Environment(undefined=StrictUndefined, autoescape=False)
    env.filters["tojson_pretty"] = _tojson_pretty
    return env.from_string(template).render(context)


def _render_html_template(template: str, context: dict[str, Any]) -> str:
    env = Environment(undefined=StrictUndefined, autoescape=True)
    env.filters["tojson_pretty"] = _tojson_pretty
    return env.from_string(template or default_html_template()).render(context)


def _tojson_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


@lru_cache
def _referenced_schema_registry() -> Registry:
    registry = Registry()
    for schema in _known_referenced_json_schemas():
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


def _known_referenced_json_schemas() -> tuple[dict[str, Any], ...]:
    try:
        from .acas_project_artifacts import acas_shared_json_schemas
    except ImportError:
        return ()
    return acas_shared_json_schemas()


def _output_instruction(output_path: str | None) -> str:
    if not output_path:
        return ""
    temp_path = f"{output_path}.tmp"
    return (
        f"不要把 JSON 输出到聊天窗口；必须把最终 JSON 一次性写入文件 {output_path}。"
        f" 推荐先写临时文件 {temp_path}，校验 JSON 后用 mv {temp_path} {output_path} 原子替换。"
        " 写入后只回复一句 artifact JSON saved，不要附带 JSON 内容。"
    )
