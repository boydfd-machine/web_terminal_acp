from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

from .template_plugin import ArtifactPluginComponents, components_from_module, default_html_template

TEMPLATE_PLUGIN_FILE = "plugin.py"
TEMPLATE_PROMPT_FILE = "prompt.jinja"
TEMPLATE_HTML_FILE = "display.html.jinja"
TEMPLATE_SCHEMA_FILE = "schema.json"
TEMPLATE_PREVIEW_FILE = "preview.json"


def is_template_plugin_dir(path: Path) -> bool:
    return path.is_dir() and (path / TEMPLATE_PLUGIN_FILE).is_file()


def load_components_from_directory(path: Path) -> ArtifactPluginComponents:
    python_source = _read_required_text(path / TEMPLATE_PLUGIN_FILE, "python code")
    prompt_template = _read_required_text(path / TEMPLATE_PROMPT_FILE, "prompt template")
    html_template = _read_optional_text(path / TEMPLATE_HTML_FILE) or default_html_template()
    json_schema = _read_json_object(path / TEMPLATE_SCHEMA_FILE, "JSON schema", required=True)
    preview_content_json = _read_json_object(path / TEMPLATE_PREVIEW_FILE, "preview data", required=False)
    return components_from_parts(
        python_source=python_source,
        prompt_template=prompt_template,
        html_template=html_template,
        json_schema=json_schema,
        preview_content_json=preview_content_json,
        root=path,
    )


def components_from_parts(
    *,
    python_source: str,
    prompt_template: str,
    html_template: str,
    json_schema: dict[str, Any],
    preview_content_json: dict[str, Any] | None,
    root: Path,
) -> ArtifactPluginComponents:
    module = _load_module_from_component_source(python_source, root=root)
    return components_from_module(
        module,
        python_source=python_source,
        prompt_template=prompt_template,
        html_template=html_template,
        json_schema=json_schema,
        preview_content_json=preview_content_json,
    )


def write_component_directory(path: Path, components: ArtifactPluginComponents) -> None:
    path.mkdir(parents=True, exist_ok=True)
    write_text_atomically(path / TEMPLATE_PLUGIN_FILE, components.python_source)
    write_text_atomically(path / TEMPLATE_PROMPT_FILE, components.prompt_template)
    write_text_atomically(path / TEMPLATE_HTML_FILE, components.html_template)
    _write_json_object(path / TEMPLATE_SCHEMA_FILE, components.json_schema)
    _write_json_object(path / TEMPLATE_PREVIEW_FILE, components.preview_content_json)


def write_text_atomically(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        handle.write(source)
        temp_name = handle.name
    Path(temp_name).replace(path)


def _load_module_from_component_source(source: str, *, root: Path) -> ModuleType:
    root.mkdir(parents=True, exist_ok=True)
    temp_path = root / f".validate-components-{uuid4().hex}.py"
    try:
        temp_path.write_text(source, encoding="utf-8")
        return _load_module_from_path(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _load_module_from_path(path: Path) -> ModuleType:
    module_name = f"web_terminal_artifact_plugin_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("artifact plugin source could not be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ValueError(f"artifact plugin import failed: {exc}") from exc
    finally:
        sys.modules.pop(module_name, None)
    return module


def _read_required_text(path: Path, label: str) -> str:
    value = _read_optional_text(path)
    if value is None or not value.strip():
        raise ValueError(f"artifact plugin {label} file is required: {path.name}")
    return value


def _read_optional_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _read_json_object(path: Path, label: str, *, required: bool) -> dict[str, Any] | None:
    if not path.is_file():
        if required:
            raise ValueError(f"artifact plugin {label} file is required: {path.name}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"artifact plugin {label} is invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"artifact plugin {label} must be an object")
    return value


def _write_json_object(path: Path, value: dict[str, Any]) -> None:
    write_text_atomically(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
