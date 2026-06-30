import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  deleteProjectTodoAttachment,
  downloadProjectTodoAttachment,
  uploadProjectTodoAttachmentImage
} from "../../api";
import { useApiFailureToast } from "../../AppQueryErrorBridge";
import { useI18n } from "../../i18n";
import type {
  ProjectTodo,
  ProjectTodoAttachment,
  ProjectTodoList as ProjectTodoListPayload,
  ProjectTodoListItem
} from "../../types";
import { projectTodoDetailQueryKey, projectTodoQueryKey } from "./projectTodoPanelUtils";

type UseProjectTodoAttachmentMutationsArgs = {
  clientId: string;
  projectPath: string;
  queryKey: ReturnType<typeof projectTodoQueryKey>;
};

type UploadVariables = {
  todo: ProjectTodo | ProjectTodoListItem;
  files: File[];
};

type DeleteVariables = {
  todo: ProjectTodo;
  attachment: ProjectTodoAttachment;
};

type ProjectTodoAttachmentPreview = {
  attachment: ProjectTodoAttachment;
  downloadUrl: string;
};

export function useProjectTodoAttachmentMutations({
  clientId,
  projectPath,
  queryKey
}: UseProjectTodoAttachmentMutationsArgs) {
  const { t } = useI18n();
  const showApiFailureToast = useApiFailureToast();
  const queryClient = useQueryClient();
  const [attachmentOpenError, setAttachmentOpenError] = useState<string | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<ProjectTodoAttachmentPreview | null>(null);
  const [uploadingAttachmentTodoIds, setUploadingAttachmentTodoIds] = useState<Set<string>>(() => new Set());
  const [deletingAttachmentIds, setDeletingAttachmentIds] = useState<Set<string>>(() => new Set());
  const projectTodosQueryPrefix = projectTodoQueryKey(clientId, projectPath);
  const invalidateTodos = () => queryClient.invalidateQueries({ queryKey: projectTodosQueryPrefix });
  const setTodoAttachments = (todoId: string, attachments: ProjectTodoAttachment[]) => {
    queryClient.setQueryData<ProjectTodo>(
      projectTodoDetailQueryKey(clientId, projectPath, todoId),
      (current) => current === undefined ? current : { ...current, attachments }
    );
    queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => current === undefined
      ? current
      : {
          todos: current.todos.map((todo) => todo.id === todoId ? { ...todo, attachments } : todo)
        });
  };

  const attachmentUploadMutation = useMutation({
    mutationFn: async ({ todo, files }: UploadVariables): Promise<{ todoId: string; attachments: ProjectTodoAttachment[] }> => {
      const uploaded: ProjectTodoAttachment[] = [];
      for (const file of files) {
        uploaded.push(await uploadProjectTodoAttachmentImage(clientId, projectPath, todo.id, file));
      }
      return { todoId: todo.id, attachments: [...attachmentList(todo), ...uploaded] };
    },
    onMutate: ({ todo }) => {
      setUploadingAttachmentTodoIds((current) => new Set(current).add(todo.id));
    },
    onSuccess: ({ todoId, attachments }) => {
      setTodoAttachments(todoId, attachments);
      void invalidateTodos();
    },
    onSettled: (_data, _error, { todo }) => {
      setUploadingAttachmentTodoIds((current) => {
        const next = new Set(current);
        next.delete(todo.id);
        return next;
      });
    }
  });

  const attachmentDeleteMutation = useMutation({
    mutationFn: ({ todo, attachment }: DeleteVariables) =>
      deleteProjectTodoAttachment(clientId, projectPath, todo.id, attachment.id),
    onMutate: ({ attachment }) => {
      setDeletingAttachmentIds((current) => new Set(current).add(attachment.id));
    },
    onSuccess: (_result, { todo, attachment }) => {
      setTodoAttachments(todo.id, attachmentList(todo).filter((candidate) => candidate.id !== attachment.id));
      void invalidateTodos();
    },
    onSettled: (_data, _error, { attachment }) => {
      setDeletingAttachmentIds((current) => {
        const next = new Set(current);
        next.delete(attachment.id);
        return next;
      });
    }
  });

  const uploadAttachments = (todo: ProjectTodo | ProjectTodoListItem, files: FileList | File[]) => {
    const selectedFiles = Array.from(files);
    if (selectedFiles.length > 0) {
      attachmentUploadMutation.mutate({ todo, files: selectedFiles });
    }
  };

  const openAttachment = async (todo: ProjectTodo, attachment: ProjectTodoAttachment) => {
    try {
      setAttachmentOpenError(null);
      setAttachmentPreview(null);
      const download = await downloadProjectTodoAttachment(clientId, projectPath, todo.id, attachment.id);
      setAttachmentPreview({
        attachment: download.attachment,
        downloadUrl: download.download_url
      });
    } catch (error) {
      showApiFailureToast(error);
      setAttachmentOpenError(error instanceof Error ? error.message : t("projectTodo.attachments.openFailed"));
    }
  };

  const closeAttachmentPreview = () => setAttachmentPreview(null);

  return {
    attachmentOpenError,
    attachmentPreview,
    attachmentDeleteMutation,
    attachmentUploadMutation,
    closeAttachmentPreview,
    deletingAttachmentIds,
    openAttachment,
    uploadingAttachmentTodoIds,
    uploadAttachments
  };
}

function attachmentList(todo: ProjectTodo | ProjectTodoListItem): ProjectTodoAttachment[] {
  return todo.attachments ?? [];
}
