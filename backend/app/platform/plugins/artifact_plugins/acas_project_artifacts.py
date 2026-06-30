from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent_trace_graph import _iter_json_objects, _iter_wrapped_json_objects
from .template_plugin import (
    ArtifactPluginComponents,
    TemplateTerminalArtifactPlugin,
    components_from_module,
)
from .types import TerminalArtifactRender

_ASSET_ROOT = Path(__file__).with_name("acas_project_assets")


@dataclass(frozen=True)
class AcasProjectArtifactSpec:
    artifact_kind: str
    label: str
    default_title: str
    acas_definition_id: str
    current_kind: str
    renderer_name: str
    methodology_skill: str
    summary: str


ACAS_PROJECT_ARTIFACT_SPECS: tuple[AcasProjectArtifactSpec, ...] = (
    AcasProjectArtifactSpec(
        artifact_kind="user_journey",
        label="User Journey",
        default_title="Project user journey",
        acas_definition_id="user-journey",
        current_kind="UserJourneyCurrent",
        renderer_name="user-journey-renderer.html",
        methodology_skill="user-journey-methodology",
        summary="single reviewed user journey source truth",
    ),
    AcasProjectArtifactSpec(
        artifact_kind="flow_model",
        label="Flow Model",
        default_title="Project flow model",
        acas_definition_id="flow-model",
        current_kind="FlowModelCurrent",
        renderer_name="flow-model-renderer.html",
        methodology_skill="flow-model-methodology",
        summary="reviewed product, system, agent, and exception flows",
    ),
    AcasProjectArtifactSpec(
        artifact_kind="low_fi_prototype",
        label="Low-fi Prototype",
        default_title="Project low-fi prototype",
        acas_definition_id="low-fi-prototype",
        current_kind="LowFiPrototypeCurrent",
        renderer_name="low-fi-prototype-renderer.html",
        methodology_skill="low-fi-prototype-methodology",
        summary="reviewed runnable low-token page-set baseline",
    ),
    AcasProjectArtifactSpec(
        artifact_kind="capability_map",
        label="Capability Map",
        default_title="Project capability map",
        acas_definition_id="capability-map",
        current_kind="CapabilityMapCurrent",
        renderer_name="capability-map-renderer.html",
        methodology_skill="capability-map-methodology",
        summary="reviewed layered L1/L2 capability map",
    ),
    AcasProjectArtifactSpec(
        artifact_kind="glossary",
        label="Glossary",
        default_title="Project glossary",
        acas_definition_id="glossary",
        current_kind="GlossaryCurrent",
        renderer_name="glossary-renderer.html",
        methodology_skill="glossary-methodology",
        summary="reviewed shared vocabulary source truth",
    ),
    AcasProjectArtifactSpec(
        artifact_kind="domain_design",
        label="Domain Design",
        default_title="Project domain design",
        acas_definition_id="domain-design",
        current_kind="DomainDesignCurrent",
        renderer_name="domain-design-renderer.html",
        methodology_skill="domain-design-methodology",
        summary="reviewed bounded contexts, aggregates, events, and mappings",
    ),
    AcasProjectArtifactSpec(
        artifact_kind="ui_spec",
        label="UI Spec",
        default_title="Project UI spec",
        acas_definition_id="ui-spec",
        current_kind="UISpecCurrent",
        renderer_name="ui-spec-renderer.html",
        methodology_skill="ui-spec-methodology",
        summary="reviewed UI source truth and implementation contract",
    ),
)


class AcasProjectArtifactPlugin:
    def __init__(self, spec: AcasProjectArtifactSpec) -> None:
        self.spec = spec
        self.artifact_kind = spec.artifact_kind
        self.label = spec.label
        self.default_title = spec.default_title
        self._template_plugin: TemplateTerminalArtifactPlugin | None = None

    def build_prompt(
        self,
        *,
        source_title: str,
        user_prompt: str | None = None,
        output_path: str | None = None,
    ) -> str:
        return self._plugin().build_prompt(
            source_title=source_title,
            user_prompt=user_prompt,
            output_path=output_path,
        )

    def parse_output(self, output: str) -> dict:
        last_error: str | None = None
        for candidate in (*_iter_json_objects(output), *_iter_wrapped_json_objects(output)):
            try:
                return self._plugin().parse_output(json.dumps(candidate, ensure_ascii=False))
            except ValueError as exc:
                last_error = str(exc)
        if last_error:
            raise ValueError(f"{self.artifact_kind} JSON did not match schema: {last_error}")
        raise ValueError(f"{self.artifact_kind} JSON was not found in terminal output")

    def render(self, content_json: dict) -> TerminalArtifactRender:
        return self._plugin().render(content_json)

    def initial_content(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.artifact_kind == "user_journey":
            return _user_journey_raw_initial_content(context or {})
        return {"kind": self.spec.current_kind, "layer": "Current"}

    def components(self) -> ArtifactPluginComponents:
        return acas_project_artifact_components(self.spec)

    def _plugin(self) -> TemplateTerminalArtifactPlugin:
        if self._template_plugin is None:
            self._template_plugin = TemplateTerminalArtifactPlugin(self.components())
        return self._template_plugin


def acas_project_artifact_plugins() -> tuple[AcasProjectArtifactPlugin, ...]:
    return tuple(AcasProjectArtifactPlugin(spec) for spec in ACAS_PROJECT_ARTIFACT_SPECS)


def acas_project_artifact_components(spec: AcasProjectArtifactSpec) -> ArtifactPluginComponents:
    return components_from_module(
        _ComponentModule(spec),
        python_source=_python_source(spec),
        prompt_template=_prompt_template(spec),
        html_template=_html_template(spec),
        json_schema=_schema_asset(spec),
        preview_content_json=_json_asset(spec, "preview/current.json"),
    )


def acas_shared_json_schemas() -> tuple[dict[str, Any], ...]:
    return (
        _json_file(_ASSET_ROOT / "_shared/review-decision/schemas/clarification-question.schema.json"),
        _json_file(_ASSET_ROOT / "_shared/review-decision/schemas/decision-review.schema.json"),
        _json_file(_ASSET_ROOT / "_shared/review-decision/schemas/decision-trace.schema.json"),
        _json_file(_ASSET_ROOT / "_shared/principle/schemas/principle-set.schema.json"),
    )


class _ComponentModule:
    def __init__(self, spec: AcasProjectArtifactSpec) -> None:
        self.ARTIFACT_KIND = spec.artifact_kind
        self.LABEL = spec.label
        self.DEFAULT_TITLE = spec.default_title
        self._renderer = f"acas-{spec.acas_definition_id}"

    def metadata_json(self, _content: dict[str, Any]) -> dict[str, Any]:
        return {"renderer": self._renderer, "artifact_kind": self.ARTIFACT_KIND}


def _python_source(spec: AcasProjectArtifactSpec) -> str:
    return f'''ARTIFACT_KIND = {json.dumps(spec.artifact_kind)}
LABEL = {json.dumps(spec.label)}
DEFAULT_TITLE = {json.dumps(spec.default_title)}


def metadata_json(content):
    return {{"renderer": {json.dumps(f"acas-{spec.acas_definition_id}")}, "artifact_kind": ARTIFACT_KIND}}
'''.strip() + "\n"


def _prompt_template(spec: AcasProjectArtifactSpec) -> str:
    if spec.artifact_kind == "user_journey":
        return _user_journey_prompt_template(spec)
    return (
        f"Use ${spec.methodology_skill} to update the project-level ACAS {spec.label} "
        f"Current artifact for terminal \"{{{{ source_title }}}}\". Produce the {spec.current_kind} "
        f"JSON only: it must preserve the reviewed Current layer as {spec.summary}. "
        "Do not output Markdown fences, HTML, YAML, or screenshots. "
        "Output only valid JSON matching this exact schema: {{ json_schema_text }}. "
        "{{ output_instruction }} Stop after producing the artifact."
        "{% if user_prompt %} User requirements: {{ user_prompt }}{% endif %}"
    )


def _user_journey_prompt_template(spec: AcasProjectArtifactSpec) -> str:
    return (
        f"Use ${spec.methodology_skill} and preserve the ACAS User Journey layered artifact "
        "contract for terminal \"{{ source_title }}\". User Journey is a user-fact model, not a UI flow, "
        "internal process map, delivery plan, or implementation plan. Produce exactly one ACAS User Journey "
        "layer JSON object matching this schema union: Raw, Competitor Research, Exploration, Decision, "
        "Principle, or Current. Follow the ACAS layer flow: Raw captures original inputs and the research gate; "
        "Competitor Research exists when the Raw gate says research is recommended or required; Exploration "
        "contains 2-4 candidate journeys plus batched clarification questions; Decision records the reviewed "
        "Exploration-to-Current payload; Current contains exactly one reviewed source-truth journey; Principle "
        "is optional and only for durable reviewed journey constraints. Do not skip directly to Current unless "
        "the prompt or existing context includes the reviewed selection, clarification answers, user edits, "
        "and synthesis rationale required by ACAS. Do not output Markdown fences, HTML, YAML, or screenshots. "
        "Output only valid JSON matching this exact schema: {{ json_schema_text }}. "
        "{{ output_instruction }} Stop after producing the artifact."
        "{% if user_prompt %} User requirements: {{ user_prompt }}{% endif %}"
    )


def _user_journey_raw_initial_content(context: dict[str, Any]) -> dict[str, Any]:
    title = _context_text(context, "project_todo_title", "todo_title")
    description = _context_text(context, "project_todo_description", "todo_description")
    dispatch_prompt = _context_text(context, "project_todo_dispatch_prompt", "dispatch_prompt")
    requested_artifact = _context_text(
        context,
        "project_todo_requested_artifact",
        "requested_artifact",
        default="project:user_journey",
    )
    project_path = _context_text(context, "project_todo_project_path", "project_path")
    source_title = _context_text(context, "source_title")
    content_lines = [
        f"Todo: {title}" if title else "",
        f"Description: {description}" if description else "",
        f"Dispatch prompt: {dispatch_prompt}" if dispatch_prompt else "",
        f"Requested artifact: {requested_artifact}" if requested_artifact else "",
        f"Project path: {project_path}" if project_path else "",
        f"Source terminal: {source_title}" if source_title else "",
    ]
    content = "\n".join(line for line in content_lines if line).strip()
    if not content:
        content = "Fresh project User Journey requested without prior reviewed artifact context."
    return {
        "kind": "UserJourneyRaw",
        "layer": "Raw",
        "rawInputs": [
            {
                "inputId": "project_todo_request",
                "sourceType": "user_text",
                "content": content,
            }
        ],
        "preservedSignals": [
            {
                "text": "A project-level User Journey artifact was requested from todo context.",
                "sourceInputId": "project_todo_request",
                "noteType": "explicit",
            }
        ],
        "researchGate": {
            "competitorResearchNeeded": "unknown",
            "urgency": "recommended",
            "reason": (
                "Fresh project-level user journey generation should begin from Raw and preserve "
                "unknowns until Exploration or review resolves them."
            ),
        },
    }


def _context_text(context: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _html_template(spec: AcasProjectArtifactSpec) -> str:
    html = _text_asset(spec, f"renderers/{spec.renderer_name}")
    bootstrap = (
        '<script>\n'
        'window.__ACAS_RENDER_RESOURCE__ = {"resource":{"content":{{ content | tojson_pretty | safe }}}};\n'
        'window.addEventListener("load", function(){\n'
        '  window.postMessage({type:"acas-render-resource",resource:{content:'
        '{{ content | tojson_pretty | safe }} }}, "*");\n'
        '});\n'
        '</script>\n'
    )
    return html.replace("</head>", bootstrap + "</head>", 1)


def _schema_asset(spec: AcasProjectArtifactSpec) -> dict[str, Any]:
    if spec.artifact_kind != "user_journey":
        return _json_asset(spec, "schemas/current.schema.json")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://acas.local/artifact-definitions/user-journey/layered-artifact.schema.json",
        "title": "User Journey Layered Artifact",
        "description": (
            "ACAS User Journey accepts Raw, Competitor Research, Exploration, "
            "Decision, Principle, and Current layer payloads."
        ),
        "oneOf": [
            _json_asset(spec, "schemas/raw.schema.json"),
            _json_asset(spec, "schemas/competitor-research.schema.json"),
            _json_asset(spec, "schemas/exploration.schema.json"),
            _json_file(_ASSET_ROOT / "_shared/review-decision/schemas/decision-review.schema.json"),
            _json_file(_ASSET_ROOT / "_shared/principle/schemas/principle-set.schema.json"),
            _json_asset(spec, "schemas/current.schema.json"),
        ],
    }


def _json_asset(spec: AcasProjectArtifactSpec, relative_path: str) -> dict[str, Any]:
    return _json_file(_ASSET_ROOT / spec.acas_definition_id / relative_path)


def _text_asset(spec: AcasProjectArtifactSpec, relative_path: str) -> str:
    return (_ASSET_ROOT / spec.acas_definition_id / relative_path).read_text(encoding="utf-8")


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"ACAS artifact asset must be a JSON object: {path}")
    return value
