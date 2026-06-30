from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .component_storage import components_from_parts
from .management import ArtifactPluginSource
from .template_plugin import TemplateTerminalArtifactPlugin


def render_source_preview_html(source: ArtifactPluginSource) -> str:
    if source.plugin_format != "template":
        raise ValueError("artifact plugin preview requires template components")
    if (
        source.python_source is None
        or source.prompt_template is None
        or source.html_template is None
        or source.json_schema is None
    ):
        raise ValueError("artifact plugin components are incomplete")
    return render_component_preview_html(
        python_source=source.python_source,
        prompt_template=source.prompt_template,
        html_template=source.html_template,
        json_schema=source.json_schema,
        preview_content_json=source.preview_content_json,
    )


def render_component_preview_html(
    *,
    python_source: str,
    prompt_template: str,
    html_template: str,
    json_schema: dict[str, Any],
    preview_content_json: dict[str, Any] | None,
) -> str:
    with tempfile.TemporaryDirectory(prefix="artifact-plugin-preview-") as temp_dir:
        components = components_from_parts(
            python_source=python_source,
            prompt_template=prompt_template,
            html_template=html_template,
            json_schema=json_schema,
            preview_content_json=preview_content_json,
            root=Path(temp_dir),
        )
    rendered = TemplateTerminalArtifactPlugin(components).render(components.preview_content_json)
    return rendered.display_html or ""
