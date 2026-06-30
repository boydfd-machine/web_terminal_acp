import type { DragEvent } from "react";

import type { ProjectTodoArtifact, ProjectTodoListItem, ProjectTodoStatus, WorkStatus } from "../types";

export type ProjectTodoCardSharedProps = {
  agentWorkStatusByWindowId: Map<string, WorkStatus>;
  busy: boolean;
  clientId: string;
  commentingTodoIds: Set<string>;
  dispatchErrors: Record<string, string>;
  dispatchingTodoIds: Set<string>;
  draggingTodoId: string | null;
  highlightedParentTodoId: string | null;
  mergeTargetTodoId: string | null;
  projectPath: string;
  selectedTodoId: string | null;
  registerTodoRef: (todoId: string, element: HTMLElement | null) => void;
  onDragEnd: () => void;
  onDragStart: (event: DragEvent<HTMLElement>, todo: ProjectTodoListItem) => void;
  onMergeDragEnter: (event: DragEvent<HTMLElement>, todo: ProjectTodoListItem) => void;
  onMergeDragLeave: (event: DragEvent<HTMLElement>, todo: ProjectTodoListItem) => void;
  onMergeDragOver: (event: DragEvent<HTMLElement>, todo: ProjectTodoListItem) => void;
  onMergeDrop: (event: DragEvent<HTMLElement>, todo: ProjectTodoListItem) => void;
  onComment: (todo: ProjectTodoListItem) => void;
  onCreateChildTodo: (todo: ProjectTodoListItem) => void;
  onDispatch: (todo: ProjectTodoListItem) => void;
  onOpenTodo: (todoId: string) => void;
  onOpenTerminalWindow: (windowId: string, projectPath: string, title?: string | null) => void;
  onShowChildTodos: (todo: ProjectTodoListItem) => void;
  onRetryArtifact: (todo: ProjectTodoListItem, artifact: ProjectTodoArtifact) => void;
  onToggleSchedule: (todo: ProjectTodoListItem, enabled: boolean) => void;
  onUploadAttachment: (todo: ProjectTodoListItem, files: FileList | File[]) => void;
  retryingArtifactLinkId: string | null;
  uploadingAttachmentTodoIds: Set<string>;
};

export type ProjectTodoBoardProps = {
  agentWorkStatusByWindowId: Map<string, WorkStatus>;
  busy: boolean;
  clientId: string;
  commentingTodoIds: Set<string>;
  dispatchErrors: Record<string, string>;
  dispatchingTodoIds: Set<string>;
  initialLoading: boolean;
  projectPath: string;
  selectedTodoId: string | null;
  todos: ProjectTodoListItem[];
  registerTodoRef: (todoId: string, element: HTMLElement | null) => void;
  onCreateChildTodo: (todo: ProjectTodoListItem) => void;
  onCreateTodo: () => void;
  onComment: (todo: ProjectTodoListItem) => void;
  onDispatch: (todo: ProjectTodoListItem) => void;
  onMergeTodo: (sourceTodoId: string, targetTodoId: string) => void;
  onMoveTodo: (todoId: string, status: ProjectTodoStatus) => void;
  onOpenTodo: (todoId: string) => void;
  onOpenTerminalWindow: (windowId: string, projectPath: string, title?: string | null) => void;
  onRetryArtifact: (todo: ProjectTodoListItem, artifact: ProjectTodoArtifact) => void;
  onToggleSchedule: (todo: ProjectTodoListItem, enabled: boolean) => void;
  onUploadAttachment: (todo: ProjectTodoListItem, files: FileList | File[]) => void;
  retryingArtifactLinkId: string | null;
  uploadingAttachmentTodoIds: Set<string>;
};

export type ProjectTodoViewSettings = {
  progress: boolean;
  totals: boolean;
  participants: boolean;
};
