from __future__ import annotations

import importlib.util
import inspect
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal
from uuid import uuid4

from .agent_trace_graph import AgentTraceGraphArtifactPlugin
from .builtin_component_sources import builtin_artifact_plugin_source_body
from .component_storage import (
    components_from_parts,
    is_template_plugin_dir,
    load_components_from_directory,
    write_component_directory,
    write_text_atomically,
)
from .template_plugin import TemplateTerminalArtifactPlugin
from .types import TerminalArtifactPlugin

ArtifactPluginDomain = Literal["terminal", "project"]
ArtifactPluginFormat = Literal["legacy_python", "template"]
_ARTIFACT_KIND_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ArtifactPluginSource:
    domain: ArtifactPluginDomain
    artifact_kind: str
    label: str
    default_title: str
    origin: Literal["built_in", "managed"]
    editable: bool
    plugin_format: ArtifactPluginFormat
    path: Path | None
    source: str | None = None
    python_source: str | None = None
    prompt_template: str | None = None
    html_template: str | None = None
    json_schema: dict[str, Any] | None = None
    preview_content_json: dict[str, Any] | None = None
    preview_content_json_by_locale: dict[str, dict[str, Any]] | None = None
    validation_error: str | None = None


def builtin_terminal_artifact_plugins() -> tuple[TerminalArtifactPlugin, ...]:
    return builtin_artifact_plugins("terminal")


def builtin_artifact_plugins(domain: ArtifactPluginDomain) -> tuple[TerminalArtifactPlugin, ...]:
    if domain == "project":
        return ()
    return (
        AgentTraceGraphArtifactPlugin(),
    )


def managed_artifact_plugins_root(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".web-terminal-acp" / "artifact-plugins"


def terminal_artifact_plugins_root(home: Path | None = None) -> Path:
    return artifact_plugins_root("terminal", home=home)


def artifact_plugins_root(domain: ArtifactPluginDomain, *, home: Path | None = None) -> Path:
    return managed_artifact_plugins_root(home) / domain


def load_managed_terminal_artifact_plugins(*, home: Path | None = None) -> tuple[TerminalArtifactPlugin, ...]:
    return load_managed_artifact_plugins("terminal", home=home)


def load_managed_artifact_plugins(
    domain: ArtifactPluginDomain,
    *,
    home: Path | None = None,
) -> tuple[TerminalArtifactPlugin, ...]:
    root = artifact_plugins_root(domain, home=home)
    if not root.is_dir():
        return ()
    plugins: list[TerminalArtifactPlugin] = []
    seen: set[str] = set()
    for path in _iter_managed_plugin_paths(root):
        try:
            plugin = _load_terminal_plugin_from_managed_path(path)
        except ValueError:
            continue
        normalized = _normal_kind(plugin.artifact_kind)
        if normalized in seen:
            continue
        seen.add(normalized)
        plugins.append(plugin)
    return tuple(plugins)


def list_artifact_plugin_sources(*, home: Path | None = None) -> list[ArtifactPluginSource]:
    builtin_sources = [
        _builtin_source(plugin, domain=domain)
        for domain in ("terminal", "project")
        for plugin in builtin_artifact_plugins(domain)
    ]
    managed_sources = [
        source
        for domain in ("terminal", "project")
        for source in _managed_sources(domain, home=home)
    ]
    return sorted(
        [*builtin_sources, *managed_sources],
        key=lambda item: (item.domain, item.origin != "built_in", item.artifact_kind.lower()),
    )


def get_artifact_plugin_source(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    *,
    home: Path | None = None,
) -> ArtifactPluginSource:
    normalized = _normal_kind(artifact_kind)
    for source in list_artifact_plugin_sources(home=home):
        if source.domain == domain and _normal_kind(source.artifact_kind) == normalized:
            if _source_needs_body(source):
                return _source_with_body(source)
            return source
    raise FileNotFoundError(f"artifact plugin not found: {artifact_kind}")


def save_terminal_artifact_plugin_source(
    source: str,
    *,
    expected_artifact_kind: str | None = None,
    allow_overwrite: bool,
    require_existing: bool = False,
    home: Path | None = None,
) -> ArtifactPluginSource:
    return save_artifact_plugin_source(
        "terminal",
        source,
        expected_artifact_kind=expected_artifact_kind,
        allow_overwrite=allow_overwrite,
        require_existing=require_existing,
        home=home,
    )


def save_artifact_plugin_source(
    domain: ArtifactPluginDomain,
    source: str,
    *,
    expected_artifact_kind: str | None = None,
    allow_overwrite: bool,
    require_existing: bool = False,
    home: Path | None = None,
) -> ArtifactPluginSource:
    root = artifact_plugins_root(domain, home=home)
    root.mkdir(parents=True, exist_ok=True)
    plugin = _load_terminal_plugin_from_source(source, root=root)
    _validate_artifact_kind(plugin.artifact_kind)
    if expected_artifact_kind is not None and _normal_kind(plugin.artifact_kind) != _normal_kind(expected_artifact_kind):
        raise ValueError("artifact_kind in source does not match route")
    _reject_builtin_duplicate(domain, plugin.artifact_kind)
    normalized = _normal_kind(plugin.artifact_kind)
    target = root / f"{normalized}.py"
    component_target = root / normalized
    if require_existing and not (target.exists() or component_target.exists()):
        raise FileNotFoundError(f"artifact plugin not found: {plugin.artifact_kind}")
    if (target.exists() or component_target.exists()) and not allow_overwrite:
        raise FileExistsError(f"artifact plugin already exists: {plugin.artifact_kind}")
    if component_target.exists():
        if component_target.is_dir():
            shutil.rmtree(component_target)
        else:
            component_target.unlink()
    write_text_atomically(target, source)
    return get_artifact_plugin_source(domain, plugin.artifact_kind, home=home)


def save_terminal_artifact_plugin_components(
    *,
    python_source: str,
    prompt_template: str,
    html_template: str,
    json_schema: dict[str, Any],
    preview_content_json: dict[str, Any] | None = None,
    expected_artifact_kind: str | None = None,
    allow_overwrite: bool,
    require_existing: bool = False,
    home: Path | None = None,
) -> ArtifactPluginSource:
    return save_artifact_plugin_components(
        "terminal",
        python_source=python_source,
        prompt_template=prompt_template,
        html_template=html_template,
        json_schema=json_schema,
        preview_content_json=preview_content_json,
        expected_artifact_kind=expected_artifact_kind,
        allow_overwrite=allow_overwrite,
        require_existing=require_existing,
        home=home,
    )


def save_artifact_plugin_components(
    domain: ArtifactPluginDomain,
    *,
    python_source: str,
    prompt_template: str,
    html_template: str,
    json_schema: dict[str, Any],
    preview_content_json: dict[str, Any] | None = None,
    expected_artifact_kind: str | None = None,
    allow_overwrite: bool,
    require_existing: bool = False,
    home: Path | None = None,
) -> ArtifactPluginSource:
    root = artifact_plugins_root(domain, home=home)
    root.mkdir(parents=True, exist_ok=True)
    components = components_from_parts(
        python_source=python_source,
        prompt_template=prompt_template,
        html_template=html_template,
        json_schema=json_schema,
        preview_content_json=preview_content_json,
        root=root,
    )
    plugin = TemplateTerminalArtifactPlugin(components)
    _validate_artifact_kind(plugin.artifact_kind)
    if expected_artifact_kind is not None and _normal_kind(plugin.artifact_kind) != _normal_kind(expected_artifact_kind):
        raise ValueError("artifact_kind in source does not match route")
    _reject_builtin_duplicate(domain, plugin.artifact_kind)
    target = root / _normal_kind(plugin.artifact_kind)
    legacy_target = root / f"{_normal_kind(plugin.artifact_kind)}.py"
    if require_existing and not (target.exists() or legacy_target.exists()):
        raise FileNotFoundError(f"artifact plugin not found: {plugin.artifact_kind}")
    if not allow_overwrite and (target.exists() or legacy_target.exists()):
        raise FileExistsError(f"artifact plugin already exists: {plugin.artifact_kind}")
    if legacy_target.exists():
        legacy_target.unlink()
    write_component_directory(target, components)
    return get_artifact_plugin_source(domain, plugin.artifact_kind, home=home)


def delete_terminal_artifact_plugin_source(artifact_kind: str, *, home: Path | None = None) -> None:
    delete_artifact_plugin_source("terminal", artifact_kind, home=home)


def delete_artifact_plugin_source(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    *,
    home: Path | None = None,
) -> None:
    _validate_artifact_kind(artifact_kind)
    _reject_builtin_duplicate(domain, artifact_kind)
    root = artifact_plugins_root(domain, home=home)
    path = root / _normal_kind(artifact_kind)
    legacy_path = root / f"{_normal_kind(artifact_kind)}.py"
    if path.is_dir():
        shutil.rmtree(path)
        return
    if legacy_path.exists():
        legacy_path.unlink()
        return
    if not path.exists():
        raise FileNotFoundError(f"artifact plugin not found: {artifact_kind}")
    path.unlink()


def _managed_sources(domain: ArtifactPluginDomain, *, home: Path | None = None) -> list[ArtifactPluginSource]:
    root = artifact_plugins_root(domain, home=home)
    if not root.is_dir():
        return []
    sources: list[ArtifactPluginSource] = []
    for path in _iter_managed_plugin_paths(root):
        try:
            plugin = _load_terminal_plugin_from_managed_path(path)
            sources.append(_source_from_plugin(
                plugin,
                domain=domain,
                origin="managed",
                editable=True,
                path=path,
                plugin_format=_plugin_format_for_path(path),
            ))
        except ValueError as exc:
            sources.append(
                ArtifactPluginSource(
                    domain=domain,
                    artifact_kind=path.stem,
                    label=path.stem,
                    default_title=path.stem,
                    origin="managed",
                    editable=True,
                    plugin_format=_plugin_format_for_path(path),
                    path=path,
                    validation_error=str(exc),
                )
            )
    return sources


def _builtin_source(plugin: TerminalArtifactPlugin, *, domain: ArtifactPluginDomain) -> ArtifactPluginSource:
    path_text = inspect.getsourcefile(plugin.__class__)
    path = Path(path_text) if path_text else None
    source = path.read_text(encoding="utf-8") if path is not None and path.exists() else None
    plugin_format, component_fields = builtin_artifact_plugin_source_body(
        plugin,
        fallback_source=source,
    )
    return ArtifactPluginSource(
        domain=domain,
        artifact_kind=plugin.artifact_kind,
        label=plugin.label,
        default_title=plugin.default_title,
        origin="built_in",
        editable=False,
        plugin_format=plugin_format,
        path=path,
        **component_fields,
    )


def _source_from_plugin(
    plugin: TerminalArtifactPlugin,
    *,
    domain: ArtifactPluginDomain,
    origin: Literal["built_in", "managed"],
    editable: bool,
    path: Path | None,
    plugin_format: ArtifactPluginFormat = "legacy_python",
) -> ArtifactPluginSource:
    return ArtifactPluginSource(
        domain=domain,
        artifact_kind=plugin.artifact_kind,
        label=plugin.label,
        default_title=plugin.default_title,
        origin=origin,
        editable=editable,
        plugin_format=plugin_format,
        path=path,
    )


def _load_terminal_plugin_from_source(source: str, *, root: Path) -> TerminalArtifactPlugin:
    root.mkdir(parents=True, exist_ok=True)
    temp_path = root / f".validate-{uuid4().hex}.py"
    try:
        temp_path.write_text(source)
        return _load_terminal_plugin_from_path(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _load_terminal_plugin_from_path(path: Path) -> TerminalArtifactPlugin:
    module = _load_module_from_path(path)
    plugin = _plugin_from_module(module)
    _validate_terminal_plugin(plugin)
    return plugin


def _load_terminal_template_plugin_from_path(path: Path) -> TerminalArtifactPlugin:
    components = load_components_from_directory(path)
    plugin = TemplateTerminalArtifactPlugin(components)
    _validate_terminal_plugin(plugin)
    return plugin


def _load_terminal_plugin_from_managed_path(path: Path) -> TerminalArtifactPlugin:
    if is_template_plugin_dir(path):
        return _load_terminal_template_plugin_from_path(path)
    return _load_terminal_plugin_from_path(path)


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


def _plugin_from_module(module: ModuleType) -> TerminalArtifactPlugin:
    factory = getattr(module, "create_plugin", None)
    if callable(factory):
        value = factory()
    elif hasattr(module, "PLUGIN"):
        value = getattr(module, "PLUGIN")
    else:
        raise ValueError("artifact plugin must expose create_plugin() or PLUGIN")
    return value


def _validate_terminal_plugin(plugin: object) -> None:
    artifact_kind = getattr(plugin, "artifact_kind", None)
    label = getattr(plugin, "label", None)
    default_title = getattr(plugin, "default_title", None)
    if not isinstance(artifact_kind, str):
        raise ValueError("artifact plugin artifact_kind must be a string")
    _validate_artifact_kind(artifact_kind)
    if not isinstance(label, str) or not label.strip():
        raise ValueError("artifact plugin label must be a non-empty string")
    if not isinstance(default_title, str) or not default_title.strip():
        raise ValueError("artifact plugin default_title must be a non-empty string")
    for method_name in ("build_prompt", "parse_output", "render"):
        if not callable(getattr(plugin, method_name, None)):
            raise ValueError(f"artifact plugin must define {method_name}()")


def _validate_artifact_kind(artifact_kind: str) -> None:
    if _ARTIFACT_KIND_PATTERN.fullmatch(artifact_kind.strip()) is None:
        raise ValueError(
            "artifact_kind must start with a letter and contain only letters, numbers, underscores, or hyphens"
        )


def _reject_builtin_duplicate(domain: ArtifactPluginDomain, artifact_kind: str) -> None:
    normalized = _normal_kind(artifact_kind)
    for plugin in builtin_artifact_plugins(domain):
        if _normal_kind(plugin.artifact_kind) == normalized:
            raise ValueError(f"built-in artifact plugin cannot be overwritten: {artifact_kind}")


def _normal_kind(value: str) -> str:
    return value.strip().lower()


def _iter_managed_plugin_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.iterdir():
        if path.name.startswith("."):
            continue
        if is_template_plugin_dir(path):
            paths.append(path)
        elif path.is_file() and path.suffix == ".py":
            paths.append(path)
    return sorted(paths, key=lambda item: (_normal_kind(item.stem), item.is_file()))


def _plugin_format_for_path(path: Path) -> ArtifactPluginFormat:
    return "template" if path.is_dir() else "legacy_python"


def _source_needs_body(source: ArtifactPluginSource) -> bool:
    return (
        source.path is not None
        and source.source is None
        and source.python_source is None
        and source.validation_error is None
    )


def _source_with_body(source: ArtifactPluginSource) -> ArtifactPluginSource:
    if source.path is None:
        return source
    if source.plugin_format == "template":
        components = load_components_from_directory(source.path)
        return ArtifactPluginSource(
            **{
                **source.__dict__,
                "source": components.python_source,
                "python_source": components.python_source,
                "prompt_template": components.prompt_template,
                "html_template": components.html_template,
                "json_schema": components.json_schema,
                "preview_content_json": components.preview_content_json,
            }
        )
    text = source.path.read_text(encoding="utf-8")
    return ArtifactPluginSource(**{**source.__dict__, "source": text, "python_source": text})
