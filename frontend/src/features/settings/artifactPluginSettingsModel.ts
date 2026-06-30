import type {
  ArtifactPluginDescriptor,
  ArtifactPluginFormat,
  ArtifactPluginPayload,
  ArtifactPluginSource
} from "../../types";
import type { TranslateFn } from "../../i18n";
import type { SummaryOutputLanguage } from "../../userPreferences";

export type ArtifactPluginDraft = {
  python_source: string;
  prompt_template: string;
  html_template: string;
  json_schema_text: string;
  preview_content_text: string;
};

export type ArtifactPluginFileKind = "python" | "prompt" | "html" | "schema" | "preview";

export type ArtifactPluginFile = {
  path: string;
  label: string;
  description: string;
  kind: ArtifactPluginFileKind;
  content: string;
  editable: boolean;
  size: number;
};

const NEW_PLUGIN_PYTHON = `ARTIFACT_KIND = "custom_report"
LABEL = "Custom Report"
DEFAULT_TITLE = "Custom report"


def normalize_content(content):
    return content


def metadata_json(content):
    return {"renderer": "custom-report"}
`;

const NEW_PLUGIN_PROMPT = `Build a custom report for terminal "{{ source_title }}".
{{ output_instruction }}

Only output valid JSON matching this schema. Do not output Markdown fences.
{{ json_schema_text }}
`;

const NEW_PLUGIN_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ content.title }}</title>
</head>
<body>
  <main>
    <h1>{{ content.title }}</h1>
    <p>{{ content.summary }}</p>
  </main>
</body>
</html>`;

const NEW_PLUGIN_SCHEMA = {
  type: "object",
  required: ["artifact_kind", "title", "summary"],
  properties: {
    artifact_kind: { const: "custom_report" },
    title: { type: "string", minLength: 1 },
    summary: { type: "string", minLength: 1 }
  },
  additionalProperties: true
};

const NEW_PLUGIN_PREVIEW = {
  artifact_kind: "custom_report",
  title: "Custom report preview",
  summary: "Preview data renders here before the plugin is saved."
};

export const NEW_PLUGIN_DRAFT: ArtifactPluginDraft = {
  python_source: NEW_PLUGIN_PYTHON,
  prompt_template: NEW_PLUGIN_PROMPT,
  html_template: NEW_PLUGIN_HTML,
  json_schema_text: JSON.stringify(NEW_PLUGIN_SCHEMA, null, 2),
  preview_content_text: JSON.stringify(NEW_PLUGIN_PREVIEW, null, 2)
};

export function pluginKey(plugin: Pick<ArtifactPluginDescriptor, "domain" | "artifact_kind">): string {
  return `${plugin.domain}:${plugin.artifact_kind}`;
}

export function artifactPluginOriginLabel(plugin: ArtifactPluginDescriptor, t?: TranslateFn): string {
  if (plugin.validation_error) {
    return t?.("settings.artifacts.validationError") ?? "Validation error";
  }
  if (plugin.origin === "built_in") {
    return t?.("settings.artifacts.origin.builtin") ?? "Built-in";
  }
  return plugin.plugin_format === "template"
    ? t?.("settings.artifacts.origin.template") ?? "Managed template"
    : t?.("settings.artifacts.origin.python") ?? "Managed Python";
}

export function draftFromSource(
  source: ArtifactPluginSource | undefined,
  userPreferredLanguage: SummaryOutputLanguage = "English"
): ArtifactPluginDraft {
  if (source === undefined) {
    return NEW_PLUGIN_DRAFT;
  }
  const previewContent = previewContentForLanguage(source, userPreferredLanguage);
  return {
    python_source: source.python_source ?? source.source ?? "",
    prompt_template: source.prompt_template ?? "",
    html_template: source.html_template ?? "",
    json_schema_text: JSON.stringify(source.json_schema ?? {}, null, 2),
    preview_content_text: JSON.stringify(previewContent, null, 2)
  };
}

export function previewContentForLanguage(
  source: ArtifactPluginSource,
  userPreferredLanguage: SummaryOutputLanguage
): Record<string, unknown> {
  const locale = userPreferredLanguage === "中文" ? "zh" : "en";
  return source.preview_content_json_by_locale?.[locale]
    ?? source.preview_content_json
    ?? {};
}

export function draftSignature(draft: ArtifactPluginDraft): string {
  return JSON.stringify(draft);
}

export function draftFromUploadedText(text: string): ArtifactPluginDraft {
  try {
    const parsed = JSON.parse(text) as ArtifactPluginPayload;
    if (parsed.python_source && parsed.prompt_template && parsed.html_template && parsed.json_schema) {
      return {
        python_source: parsed.python_source,
        prompt_template: parsed.prompt_template,
        html_template: parsed.html_template,
        json_schema_text: JSON.stringify(parsed.json_schema, null, 2),
        preview_content_text: JSON.stringify(parsed.preview_content_json ?? {}, null, 2)
      };
    }
  } catch {
    // Plain Python uploads fill the Python component and keep the default templates.
  }
  return {
    ...NEW_PLUGIN_DRAFT,
    python_source: text
  };
}

export function payloadFromDraft(
  draft: ArtifactPluginDraft,
  pluginFormat: ArtifactPluginFormat
): string | ArtifactPluginPayload {
  if (pluginFormat === "legacy_python") {
    return draft.python_source;
  }
  return templatePayloadFromDraft(draft);
}

export function templatePayloadFromDraft(draft: ArtifactPluginDraft): ArtifactPluginPayload {
  return {
    python_source: draft.python_source,
    prompt_template: draft.prompt_template,
    html_template: draft.html_template,
    json_schema: JSON.parse(draft.json_schema_text) as Record<string, unknown>,
    preview_content_json: JSON.parse(draft.preview_content_text) as Record<string, unknown>
  };
}

export function schemaError(value: string, t?: TranslateFn): string | null {
  return jsonObjectError(value, "JSON Schema", t);
}

export function previewContentError(value: string, t?: TranslateFn): string | null {
  return jsonObjectError(value, "Preview data", t);
}

function jsonObjectError(value: string, label: string, t?: TranslateFn): string | null {
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)
      ? null
      : t?.("settings.artifacts.validation.object", { label }) ?? `${label} 必须是对象`;
  } catch (error) {
    return error instanceof Error ? error.message : t?.("settings.artifacts.validation.json", { label }) ?? `${label} 不是合法 JSON`;
  }
}

export function artifactPluginFiles(
  draft: ArtifactPluginDraft,
  plugin: ArtifactPluginDescriptor | null,
  pluginFormat: ArtifactPluginFormat,
  t?: TranslateFn
): ArtifactPluginFile[] {
  const editable = plugin?.editable ?? true;
  if (pluginFormat === "legacy_python") {
    const path = `${plugin?.artifact_kind ?? "custom_report"}.py`;
    return [{
      path,
      label: "Python",
      description: t?.("settings.artifacts.file.legacyPythonDescription") ?? "Legacy Python plugin source",
      kind: "python",
      content: draft.python_source,
      editable,
      size: textBytes(draft.python_source)
    }];
  }
  return [
    {
      path: "plugin.py",
      label: "Python",
      description: t?.("settings.artifacts.file.pluginDescription") ?? "Plugin metadata and normalization hooks",
      kind: "python",
      content: draft.python_source,
      editable,
      size: textBytes(draft.python_source)
    },
    {
      path: "prompt.jinja",
      label: "Prompt Jinja",
      description: t?.("settings.artifacts.file.promptDescription") ?? "Prompt template sent to the agent",
      kind: "prompt",
      content: draft.prompt_template,
      editable,
      size: textBytes(draft.prompt_template)
    },
    {
      path: "display.html.jinja",
      label: "HTML Jinja",
      description: t?.("settings.artifacts.file.htmlDescription") ?? "Rendered artifact display template",
      kind: "html",
      content: draft.html_template,
      editable,
      size: textBytes(draft.html_template)
    },
    {
      path: "schema.json",
      label: "JSON Schema",
      description: t?.("settings.artifacts.file.schemaDescription") ?? "Agent JSON validation schema",
      kind: "schema",
      content: draft.json_schema_text,
      editable,
      size: textBytes(draft.json_schema_text)
    },
    {
      path: "preview.json",
      label: "Preview JSON",
      description: t?.("settings.artifacts.file.previewDescription") ?? "Single artifact preview data",
      kind: "preview",
      content: draft.preview_content_text,
      editable,
      size: textBytes(draft.preview_content_text)
    }
  ];
}

export function draftWithFileContent(
  draft: ArtifactPluginDraft,
  file: ArtifactPluginFile,
  content: string
): ArtifactPluginDraft {
  if (file.kind === "prompt") {
    return { ...draft, prompt_template: content };
  }
  if (file.kind === "html") {
    return { ...draft, html_template: content };
  }
  if (file.kind === "schema") {
    return { ...draft, json_schema_text: content };
  }
  if (file.kind === "preview") {
    return { ...draft, preview_content_text: content };
  }
  return { ...draft, python_source: content };
}

export function textBytes(value: string): number {
  return new TextEncoder().encode(value).length;
}

export function byteLabel(size: number | null): string {
  if (size === null) {
    return "-";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
