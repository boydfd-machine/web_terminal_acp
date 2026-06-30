import { useCallback, useEffect, useRef } from "react";

import { ARTIFACT_IFRAME_SANDBOX } from "../artifactHtmlSecurity";
import {
  artifactProjectTodoCreateFailedMessage,
  artifactProjectTodoCreatedMessage,
  normalizeArtifactProjectTodoCreateMessage,
  type ArtifactProjectTodoCreateInput,
  type ArtifactProjectTodoResponseMessage
} from "../artifactProjectTodoBridge";
import { useApiFailureToast } from "../AppQueryErrorBridge";
import type { ProjectTodo } from "../types";

type ArtifactProjectTodoFrameProps = {
  artifactId?: string | null;
  clientId: string;
  projectPath: string | null;
  srcDoc: string;
  title: string;
  onCreateProjectTodo?: (
    card: ArtifactProjectTodoCreateInput,
    artifactId: string | null
  ) => Promise<ProjectTodo>;
};

export function ArtifactProjectTodoFrame({
  artifactId = null,
  clientId,
  projectPath,
  srcDoc,
  title,
  onCreateProjectTodo
}: ArtifactProjectTodoFrameProps) {
  const showApiFailureToast = useApiFailureToast();
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const latest = useRef({ artifactId, clientId, onCreateProjectTodo, projectPath });
  latest.current = { artifactId, clientId, onCreateProjectTodo, projectPath };

  const postToFrame = useCallback((message: ArtifactProjectTodoResponseMessage) => {
    iframeRef.current?.contentWindow?.postMessage(message, "*");
  }, []);

  useEffect(() => {
    function onMessage(event: MessageEvent): void {
      const frameWindow = iframeRef.current?.contentWindow;
      if (frameWindow === null || frameWindow === undefined || event.source !== frameWindow) {
        return;
      }
      const message = normalizeArtifactProjectTodoCreateMessage(event.data);
      if (message === null) {
        return;
      }
      const { artifactId, onCreateProjectTodo, projectPath } = latest.current;
      if (projectPath === null || onCreateProjectTodo === undefined) {
        postToFrame(artifactProjectTodoCreateFailedMessage(message, "project path is required"));
        return;
      }
      onCreateProjectTodo(message.card, artifactId)
        .then((todo) => postToFrame(artifactProjectTodoCreatedMessage(message, todo)))
        .catch((error: unknown) => {
          showApiFailureToast(error);
          postToFrame(artifactProjectTodoCreateFailedMessage(message, errorMessage(error)));
        });
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [postToFrame, showApiFailureToast]);

  return (
    <iframe
      ref={iframeRef}
      title={title}
      sandbox={ARTIFACT_IFRAME_SANDBOX}
      referrerPolicy="no-referrer"
      srcDoc={srcDoc}
      data-client-id={clientId}
      data-project-path={projectPath ?? ""}
      data-artifact-id={artifactId ?? ""}
    />
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "failed to create project todo";
}
