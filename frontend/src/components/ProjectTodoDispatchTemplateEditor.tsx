import { useId } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodo } from "../types";

export type ProjectTodoDispatchTemplateContext = {
  project_path: string;
  title: string;
  description: string;
  todo_type_id: string;
  artifact_kinds: string[];
};

type ProjectTodoDispatchTemplateEditorProps = {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
  rows?: number;
  compact?: boolean;
  readOnly?: boolean;
  showVariables?: boolean;
  previewContext?: ProjectTodoDispatchTemplateContext | null;
};

const TEMPLATE_VARIABLES = ["title", "description", "project_path", "todo_type_id", "artifact_kinds"] as const;

export function ProjectTodoDispatchTemplateEditor({
  value,
  onChange,
  label,
  placeholder,
  rows = 5,
  compact = false,
  readOnly = false,
  showVariables = true,
  previewContext = null
}: ProjectTodoDispatchTemplateEditorProps) {
  const { t } = useI18n();
  const textareaId = useId();
  const preview = previewContext === null || value.trim().length === 0
    ? ""
    : renderProjectTodoDispatchTemplatePreview(value, previewContext);
  const displayLabel = label ?? t("settings.cardTypes.dispatchTemplate");
  return (
    <div className={`project-todo-dispatch-template ${compact ? "compact" : ""}`}>
      <label htmlFor={textareaId}>{displayLabel}</label>
      <textarea
        id={textareaId}
        value={value}
        readOnly={readOnly}
        rows={rows}
        spellCheck={false}
        placeholder={placeholder ?? t("settings.cardTypes.defaultPromptPlaceholder")}
        onChange={(event) => onChange(event.target.value)}
      />
      {showVariables && (
        <span className="project-todo-dispatch-template-vars">
          {TEMPLATE_VARIABLES.map((variable) => (
            <code key={variable}>{`{{ ${variable} }}`}</code>
          ))}
        </span>
      )}
      {preview && (
        <details className="project-todo-dispatch-template-preview">
          <summary>{t("settings.cardTypes.preview")}</summary>
          <pre>{preview}</pre>
        </details>
      )}
    </div>
  );
}

export function projectTodoDispatchTemplateContext(
  todo: ProjectTodo,
  projectPath: string
): ProjectTodoDispatchTemplateContext {
  return {
    project_path: projectPath,
    title: todo.title,
    description: todo.description ?? "",
    todo_type_id: todo.todo_type_id,
    artifact_kinds: todo.artifact_kinds
  };
}

export function projectTodoDispatchPromptPreview(todo: ProjectTodo, projectPath: string): string {
  const template = todo.todo_type.dispatch_template?.trim();
  if (template) {
    return renderProjectTodoDispatchTemplatePreview(
      template,
      projectTodoDispatchTemplateContext(todo, projectPath)
    ).trim();
  }
  return defaultProjectTodoDispatchPrompt({
    projectPath,
    title: todo.title,
    description: todo.description
  });
}

export function renderProjectTodoDispatchTemplatePreview(
  template: string,
  context: ProjectTodoDispatchTemplateContext
): string {
  return template.replace(/\{\{\s*(title|description|project_path|todo_type_id|artifact_kinds)\s*\}\}/g, (
    _match,
    key: keyof ProjectTodoDispatchTemplateContext
  ) => {
    const value = context[key];
    return Array.isArray(value) ? value.join(", ") : value;
  });
}

function defaultProjectTodoDispatchPrompt({
  projectPath,
  title,
  description
}: {
  projectPath: string;
  title: string;
  description: string | null;
}): string {
  const sections = [
    "You are assigned to complete this project todo.",
    `Project path: ${projectPath}`,
    `Todo: ${title}`
  ];
  if (description) {
    sections.push(`Context:\n${description}`);
  }
  return sections.join("\n\n");
}
