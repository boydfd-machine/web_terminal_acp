import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createProjectTodo, createProjectTodoFromArtifactCard } from "../api";
import type { ArtifactProjectTodoCreateInput } from "../artifactProjectTodoBridge";
import { projectTodoDetailQueryKey } from "../features/projectTodos/projectTodoPanelUtils";

type ArtifactProjectTodoVariables = {
  artifactId: string | null;
  card: ArtifactProjectTodoCreateInput;
  clientId: string;
  projectPath: string;
};

type UseArtifactProjectTodoCreatorArgs = {
  onCreated?: (projectPath: string, todoId: string) => void;
  onInvalidateArtifactSource?: (clientId: string, artifactId: string | null) => void;
};

export function useArtifactProjectTodoCreator({
  onCreated,
  onInvalidateArtifactSource
}: UseArtifactProjectTodoCreatorArgs = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      artifactId,
      card,
      clientId,
      projectPath
    }: ArtifactProjectTodoVariables) => {
      if (artifactId === null) {
        return createProjectTodo(clientId, projectPath, card);
      }
      return createProjectTodoFromArtifactCard(clientId, projectPath, {
        artifact_id: artifactId,
        card,
        purpose: "artifact_card"
      });
    },
    onSuccess: (todo, variables) => {
      queryClient.setQueryData(projectTodoDetailQueryKey(variables.clientId, variables.projectPath, todo.id), todo);
      queryClient.invalidateQueries({ queryKey: ["project-todos", variables.clientId, variables.projectPath] });
      onInvalidateArtifactSource?.(variables.clientId, variables.artifactId);
      onCreated?.(todo.project_path, todo.id);
    }
  });
}
