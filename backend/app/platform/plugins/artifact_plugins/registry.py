from __future__ import annotations

from collections.abc import Iterable

from .management import (
    builtin_artifact_plugins,
    load_managed_artifact_plugins,
)
from .types import TerminalArtifactPlugin
from .user_settings_repository import artifact_plugin_settings_home


def _normal_key(value: str) -> str:
    return value.strip().lower()


class TerminalArtifactPluginRegistry:
    def __init__(self, plugins: Iterable[TerminalArtifactPlugin], *, domain: str = "terminal"):
        self._domain = domain
        self._plugins = tuple(plugins)
        self._by_kind: dict[str, TerminalArtifactPlugin] = {}
        for plugin in self._plugins:
            key = _normal_key(plugin.artifact_kind)
            if not key:
                raise ValueError(f"{domain} artifact plugin has empty artifact_kind")
            if key in self._by_kind:
                raise ValueError(f"duplicate {domain} artifact plugin kind: {plugin.artifact_kind}")
            self._by_kind[key] = plugin

    def all(self) -> tuple[TerminalArtifactPlugin, ...]:
        return self._plugins

    def by_kind(self, artifact_kind: str) -> TerminalArtifactPlugin:
        try:
            return self._by_kind[_normal_key(artifact_kind)]
        except KeyError as exc:
            raise ValueError(f"unsupported {self._domain} artifact kind: {artifact_kind}") from exc


_DEFAULT_REGISTRIES: dict[tuple[str, str | None], TerminalArtifactPluginRegistry] = {}


def get_terminal_artifact_plugin_registry(
    *,
    owner_user_id: str | None = None,
) -> TerminalArtifactPluginRegistry:
    return _registry_for_domain("terminal", owner_user_id)


def get_project_artifact_plugin_registry(
    *,
    owner_user_id: str | None = None,
) -> TerminalArtifactPluginRegistry:
    return _registry_for_domain("project", owner_user_id)


def get_artifact_plugin_registry_for_scope(
    scope: str,
    *,
    owner_user_id: str | None = None,
) -> TerminalArtifactPluginRegistry:
    if scope == "project":
        return get_project_artifact_plugin_registry(owner_user_id=owner_user_id)
    return get_terminal_artifact_plugin_registry(owner_user_id=owner_user_id)


def reset_terminal_artifact_plugin_registry() -> None:
    for key in [key for key in _DEFAULT_REGISTRIES if key[0] == "terminal"]:
        _DEFAULT_REGISTRIES.pop(key, None)


def reset_project_artifact_plugin_registry() -> None:
    for key in [key for key in _DEFAULT_REGISTRIES if key[0] == "project"]:
        _DEFAULT_REGISTRIES.pop(key, None)


def reset_artifact_plugin_registries() -> None:
    _DEFAULT_REGISTRIES.clear()


def _registry_for_domain(
    domain: str,
    owner_user_id: str | None,
) -> TerminalArtifactPluginRegistry:
    key = (domain, owner_user_id)
    if key not in _DEFAULT_REGISTRIES:
        _DEFAULT_REGISTRIES[key] = TerminalArtifactPluginRegistry(
            _default_plugins(domain, owner_user_id=owner_user_id),
            domain=domain,
        )
    return _DEFAULT_REGISTRIES[key]


def _default_plugins(
    domain: str,
    *,
    owner_user_id: str | None,
) -> tuple[TerminalArtifactPlugin, ...]:
    plugins = list(builtin_artifact_plugins(domain))
    seen = {_normal_key(plugin.artifact_kind) for plugin in plugins}
    for plugin in load_managed_artifact_plugins(
        domain,
        home=artifact_plugin_settings_home(owner_user_id),
    ):
        key = _normal_key(plugin.artifact_kind)
        if key in seen:
            continue
        seen.add(key)
        plugins.append(plugin)
    return tuple(plugins)
