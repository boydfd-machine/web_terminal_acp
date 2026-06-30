import type { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import type { ProjectTodoCreationPendingRequest, WorkspaceMode } from "../appState";
import {
  appendProjectTodoAnnotation,
  createProjectTodo,
  fetchProjectTodos,
} from "../apiProjectTodos";
import { uploadProjectTodoAttachmentImage } from "../apiProjectTodoAttachments";
import { useApiFailureToast } from "../AppQueryErrorBridge";
import type {
  PageAnnotationHost,
  PageAnnotationTodoTarget,
} from "../pageAnnotation";
import { projectPathForWindow } from "../terminalTree";
import type { ProjectTodoAttachment, ProjectTodoList, ProjectTodo } from "../types";
import type { ThemeSkinId } from "../userPreferences";

type PageAnnotationWindowContext = {
  cwd?: string | null;
  runtime_tags?: string[] | null;
} | null;

type UsePageAnnotationHostArgs = {
  clearProjectTodoCreationPendingRequest: (request: ProjectTodoCreationPendingRequest) => void;
  focusProjectTodo: (projectPath: string, todoId: string) => void;
  focusProjectTodoCreation: (projectPath: string, title: string) => ProjectTodoCreationPendingRequest | null;
  queryClient: QueryClient;
  selectedClientId: string | null;
  selectedProjectPath: string | null;
  selectedWindow: PageAnnotationWindowContext;
  selectedWindowId: string | null;
  selectWorkspaceMode: (mode: WorkspaceMode) => void;
  setArtifactQuickOpenOpen: (open: boolean) => void;
  setClientSwitcherOpen: (open: boolean) => void;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectPath: (projectPath: string | null) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setTerminalQuickInputOpen: (open: boolean) => void;
  setTerminalSwitcherOpen: (open: boolean) => void;
  themeSkin: ThemeSkinId;
  workspaceMode: WorkspaceMode;
};

export function usePageAnnotationHost(args: UsePageAnnotationHostArgs): void {
  const showApiFailureToast = useApiFailureToast();
  const {
    clearProjectTodoCreationPendingRequest,
    focusProjectTodo,
    focusProjectTodoCreation,
    queryClient,
    selectedClientId,
    selectedProjectPath,
    selectedWindow,
    selectedWindowId,
    selectWorkspaceMode,
    setArtifactQuickOpenOpen,
    setClientSwitcherOpen,
    setProjectTerminalPickerOpen,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setTerminalControlsOpen,
    setTerminalQuickInputOpen,
    setTerminalSwitcherOpen,
    themeSkin,
    workspaceMode,
  } = args;
  useEffect(() => {
    const host: PageAnnotationHost = {
      getContext: () => ({
        clientId: selectedClientId,
        projectPath: selectedAnnotationProjectPath(args),
        windowId: selectedWindowId,
        workspaceMode,
        themeSkin
      }),
      createTodo: async ({ title, description }) => {
        try {
          const { clientId, projectPath } = requireAnnotationProject(args);
          const todo = await createProjectTodo(clientId, projectPath, {
            title,
            description,
            todo_type_id: "default"
          });
          queryClient.setQueryData(["project-todo", clientId, projectPath, todo.id], todo);
          await queryClient.invalidateQueries({ queryKey: ["project-todos", clientId, projectPath] });
          return todo;
        } catch (error) {
          showApiFailureToast(error);
          throw error;
        }
      },
      beginTodoCreation: ({ title }) => {
        const { projectPath } = requireAnnotationProject(args);
        const request = focusProjectTodoCreation(projectPath, title);
        if (request === null) {
          return null;
        }
        return {
          onFailed: () => clearProjectTodoCreationPendingRequest(request)
        };
      },
      listTodos: async () => {
        try {
          const { clientId, projectPath } = requireAnnotationProject(args);
          const queryKey = ["project-todos", clientId, projectPath] as const;
          const cached = queryClient.getQueryData<ProjectTodoList>(queryKey);
          const list = cached ?? await fetchProjectTodoList(queryClient, queryKey, clientId, projectPath);
          return list.todos.map(todoTarget);
        } catch (error) {
          showApiFailureToast(error);
          throw error;
        }
      },
      appendAnnotation: async (todoId, { annotation }) => {
        try {
          const { clientId, projectPath } = requireAnnotationProject(args);
          const todo = await appendProjectTodoAnnotation(clientId, projectPath, todoId, { annotation });
          queryClient.setQueryData(["project-todo", clientId, projectPath, todo.id], todo);
          await queryClient.invalidateQueries({ queryKey: ["project-todos", clientId, projectPath] });
          return todo;
        } catch (error) {
          showApiFailureToast(error);
          throw error;
        }
      },
      uploadImage: async (todoId, file) => {
        try {
          const { clientId, projectPath } = requireAnnotationProject(args);
          const attachment = await uploadProjectTodoAttachmentImage(clientId, projectPath, todoId, file);
          appendCachedAttachment(queryClient, clientId, projectPath, todoId, attachment);
          await queryClient.invalidateQueries({ queryKey: ["project-todos", clientId, projectPath] });
        } catch (error) {
          showApiFailureToast(error);
          throw error;
        }
      },
      focusTodo: (todo) => {
        setSelectedProjectPath(todo.project_path);
        setSelectedProjectBrowseRoot(null);
        selectWorkspaceMode("kanban");
        focusProjectTodo(todo.project_path, todo.id);
      },
      closeCompetingOverlays: () => {
        setTerminalControlsOpen(false);
        setTerminalQuickInputOpen(false);
        setTerminalSwitcherOpen(false);
        setClientSwitcherOpen(false);
        setArtifactQuickOpenOpen(false);
        setProjectTerminalPickerOpen(false);
      }
    };
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ = host;
    return () => {
      if (window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ === host) {
        delete window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__;
      }
    };
  }, [
    clearProjectTodoCreationPendingRequest,
    focusProjectTodo,
    focusProjectTodoCreation,
    queryClient,
    selectedClientId,
    selectedProjectPath,
    selectedWindow,
    selectedWindowId,
    selectWorkspaceMode,
    setArtifactQuickOpenOpen,
    setClientSwitcherOpen,
    setProjectTerminalPickerOpen,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setTerminalControlsOpen,
    setTerminalQuickInputOpen,
    setTerminalSwitcherOpen,
    themeSkin,
    workspaceMode,
  ]);
}

function fetchProjectTodoList(
  queryClient: QueryClient,
  queryKey: readonly ["project-todos", string, string],
  clientId: string,
  projectPath: string
): Promise<ProjectTodoList> {
  return queryClient.fetchQuery({
    queryKey,
    queryFn: () => fetchProjectTodos(clientId, projectPath)
  });
}

function selectedAnnotationProjectPath(args: UsePageAnnotationHostArgs): string | null {
  return args.selectedProjectPath ?? projectPathForWindow(args.selectedWindow);
}

function requireAnnotationProject(args: UsePageAnnotationHostArgs): {
  clientId: string;
  projectPath: string;
} {
  const projectPath = selectedAnnotationProjectPath(args);
  if (args.selectedClientId === null || projectPath === null) {
    throw new Error("Select a project before creating an annotation card.");
  }
  return { clientId: args.selectedClientId, projectPath };
}

function todoTarget(todo: ProjectTodoList["todos"][number]): PageAnnotationTodoTarget {
  return {
    id: todo.id,
    title: todo.title,
    status: todo.status,
  };
}

function appendCachedAttachment(
  queryClient: QueryClient,
  clientId: string,
  projectPath: string,
  todoId: string,
  attachment: ProjectTodoAttachment
): void {
  queryClient.setQueryData<ProjectTodo>(
    ["project-todo", clientId, projectPath, todoId],
    (current) => current === undefined ? current : {
      ...current,
      attachments: [...(current.attachments ?? []), attachment]
    }
  );
  queryClient.setQueryData<ProjectTodoList>(
    ["project-todos", clientId, projectPath],
    (current) => current === undefined ? current : {
      todos: current.todos.map((todo) => todo.id === todoId
        ? { ...todo, attachments: [...(todo.attachments ?? []), attachment] }
        : todo)
    }
  );
}
