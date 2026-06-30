import type { ProjectTodo, ProjectTodoListItem } from "./types";
import type { PageAnnotationEvidence, PageAnnotationRect } from "./pageAnnotationEvidence";

export type PageAnnotationPoint = {
  x: number;
  y: number;
};

export type PageAnnotationContext = {
  clientId: string | null;
  projectPath: string | null;
  windowId: string | null;
  workspaceMode: string;
  themeSkin?: string;
};

export type PageAnnotationTodoInput = {
  title: string;
  description: string;
};

export type PageAnnotationPendingTodoCreation = {
  onFailed: () => void;
};

export type PageAnnotationHost = {
  getContext: () => PageAnnotationContext;
  createTodo: (input: PageAnnotationTodoInput) => Promise<ProjectTodo>;
  listTodos?: () => Promise<PageAnnotationTodoTarget[]>;
  appendAnnotation?: (todoId: string, input: { annotation: string }) => Promise<ProjectTodo>;
  uploadImage?: (todoId: string, file: File) => Promise<void>;
  beginTodoCreation?: (input: PageAnnotationTodoInput) => PageAnnotationPendingTodoCreation | null;
  focusTodo?: (todo: ProjectTodo) => void;
  closeCompetingOverlays?: () => void;
};

export type PageAnnotationTodoTarget = Pick<ProjectTodoListItem, "id" | "title" | "status">;

declare global {
  interface Window {
    __WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__?: boolean;
    __WEB_TERMINAL_PAGE_ANNOTATION_HOST__?: PageAnnotationHost;
  }
}

const MIN_SELECTION_SIZE = 8;
const MAX_TITLE_LENGTH = 80;

export function normalizePageAnnotationSelection(
  start: PageAnnotationPoint,
  end: PageAnnotationPoint
): PageAnnotationRect | null {
  const left = Math.min(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const width = Math.abs(end.x - start.x);
  const height = Math.abs(end.y - start.y);
  if (width < MIN_SELECTION_SIZE || height < MIN_SELECTION_SIZE) {
    return null;
  }
  return {
    left: Math.round(left),
    top: Math.round(top),
    width: Math.round(width),
    height: Math.round(height)
  };
}

export function buildPageAnnotationTodoInput({
  evidence,
  userCommand
}: {
  evidence: PageAnnotationEvidence;
  userCommand: string;
}): PageAnnotationTodoInput {
  const normalizedCommand = userCommand.trim();
  const commandText = normalizedCommand.length > 0 ? normalizedCommand : "No user command provided.";
  return {
    title: buildPageAnnotationTitle(commandText, evidence),
    description: buildPageAnnotationDescription(commandText, evidence)
  };
}

function buildPageAnnotationTitle(commandText: string, evidence: PageAnnotationEvidence): string {
  if (commandText !== "No user command provided.") {
    const firstLine = commandText.split(/\r?\n/).find((line) => line.trim().length > 0)?.trim() ?? "";
    if (firstLine.length > 0) {
      return `Annotation: ${truncate(firstLine, MAX_TITLE_LENGTH - 12)}`;
    }
  }
  const fallback = evidence.route || evidence.appState.workspaceMode || "selected page area";
  return `Annotation: ${truncate(fallback, MAX_TITLE_LENGTH - 12)}`;
}

function buildPageAnnotationDescription(commandText: string, evidence: PageAnnotationEvidence): string {
  const lines = [
    "Source: Debug page annotation",
    `Route: ${evidence.route}`,
    `Workspace mode: ${evidence.appState.workspaceMode}`,
    `Client: ${evidence.appState.clientId ?? "none"}`,
    `Project path: ${evidence.appState.projectPath ?? "none"}`,
    `Window: ${evidence.appState.windowId ?? "none"}`,
    `Theme skin: ${evidence.appState.themeSkin ?? "unknown"}`,
    `Viewport: ${evidence.viewport.width}x${evidence.viewport.height} @ devicePixelRatio ${evidence.viewport.devicePixelRatio}`,
    selectionLine(evidence.selection),
    "",
    "Primary target:",
    ...primaryTargetLines(evidence.primaryTarget),
    "",
    "DOM ancestry:",
    ...listLines(evidence.primaryTarget?.ancestry ?? []),
    "",
    "Computed style summary:",
    ...recordLines(evidence.primaryTarget?.style ?? {}),
    "",
    "Follow the user's command:",
    commandText
  ];
  return lines.join("\n");
}

function primaryTargetLines(target: PageAnnotationEvidence["primaryTarget"]): string[] {
  if (target === null) {
    return ["- none"];
  }
  return [
    `- selector: ${target.selector}`,
    `- selector confidence: ${target.selectorConfidence}`,
    `- tag: ${target.tagName}`,
    `- role/name: ${target.role ?? "none"} / ${target.accessibleName ?? "none"}`,
    `- text: ${target.text || "none"}`,
    `- classes: ${target.classNames.length > 0 ? target.classNames.join(" ") : "none"}`,
    `- attributes: ${formatRecord(target.safeAttributes)}`,
    `- rect: ${selectionLine(target.rect).replace(/^Selection: /, "")}`
  ];
}

function selectionLine(rect: PageAnnotationRect): string {
  return `Selection: x=${rect.left}, y=${rect.top}, width=${rect.width}, height=${rect.height}`;
}

function listLines(values: string[]): string[] {
  return values.length > 0 ? values.map((value) => `- ${value}`) : ["- none"];
}

function recordLines(record: Record<string, string>): string[] {
  const entries = Object.entries(record);
  return entries.length > 0 ? entries.map(([key, value]) => `- ${key}: ${value}`) : ["- none"];
}

function formatRecord(record: Record<string, string>): string {
  const entries = Object.entries(record);
  return entries.length === 0
    ? "none"
    : entries.map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(", ");
}

function truncate(value: string, maxLength: number): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength - 1)}...`;
}
