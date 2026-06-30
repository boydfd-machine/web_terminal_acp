import { useI18n } from "../i18n";
import type { ProjectTodoReference } from "../types";
import { projectTodoStatusLabel, projectTodoStatusClass } from "./projectTodoDisplay";

const PROJECT_TODO_REFERENCE_RE = /@\[ *(?:其他需求|其它需求) *[：:] *\$([^\]\r\n]+?) *\]/gu;

type ProjectTodoDescriptionTextProps = {
  description: string | null | undefined;
  referencedTodos: ProjectTodoReference[];
  emptyText?: string;
  onOpenTodo: (todoId: string) => void;
};

type DescriptionPart =
  | { kind: "text"; text: string }
  | { kind: "reference"; raw: string; title: string; todoId: string | null };

export function ProjectTodoDescriptionText({
  description,
  referencedTodos,
  emptyText,
  onOpenTodo
}: ProjectTodoDescriptionTextProps) {
  const { t } = useI18n();
  const displayEmptyText = emptyText ?? t("projectTodo.description.noDescription");
  const text = description?.trim() ? description : "";
  if (!text) {
    return <span className="muted">{displayEmptyText}</span>;
  }

  const referencesByTitle = new Map(referencedTodos.map((todo) => [todo.title, todo]));
  const referencesById = new Map(referencedTodos.map((todo) => [todo.id, todo]));
  return (
    <>
      {projectTodoDescriptionParts(text).map((part, index) => {
        if (part.kind === "text") {
          return <span key={`${index}-text`}>{part.text}</span>;
        }
        const reference = part.todoId === null
          ? referencesByTitle.get(part.title)
          : referencesById.get(part.todoId);
        if (reference === undefined) {
          return <span key={`${index}-missing`}>{part.raw}</span>;
        }
        return (
          <span key={`${index}-${reference.id}`} className="project-todo-reference-shell">
            <button
              type="button"
              className="project-todo-reference-link"
              onClick={() => onOpenTodo(reference.id)}
            >
              {reference.title}
            </button>
            <span className="project-todo-reference-preview" role="tooltip">
              <strong>{reference.title}</strong>
              <span className={`project-todo-status-pill ${projectTodoStatusClass(reference.status)}`}>
                {projectTodoStatusLabel(reference.status, t)}
              </span>
              <span>{reference.description?.trim() || displayEmptyText}</span>
            </span>
          </span>
        );
      })}
    </>
  );
}

export function projectTodoDescriptionParts(description: string): DescriptionPart[] {
  const parts: DescriptionPart[] = [];
  let lastIndex = 0;
  PROJECT_TODO_REFERENCE_RE.lastIndex = 0;
  for (const match of description.matchAll(PROJECT_TODO_REFERENCE_RE)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      parts.push({ kind: "text", text: description.slice(lastIndex, index) });
    }
    const reference = projectTodoReferenceFromBody(match[1] ?? "");
    if (reference !== null) {
      parts.push({ kind: "reference", raw: match[0], ...reference });
    } else {
      parts.push({ kind: "text", text: match[0] });
    }
    lastIndex = index + match[0].length;
  }
  if (lastIndex < description.length) {
    parts.push({ kind: "text", text: description.slice(lastIndex) });
  }
  return parts;
}

function projectTodoReferenceFromBody(body: string): { title: string; todoId: string | null } | null {
  const value = body.trim();
  if (!value) {
    return null;
  }
  const separator = value.lastIndexOf("|");
  if (separator < 0) {
    return { title: value, todoId: null };
  }
  const title = value.slice(0, separator).trim();
  const todoId = value.slice(separator + 1).trim();
  if (!title || !isUuid(todoId)) {
    return { title: value, todoId: null };
  }
  return { title, todoId };
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(value);
}
