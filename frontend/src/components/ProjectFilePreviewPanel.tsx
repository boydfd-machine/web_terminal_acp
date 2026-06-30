import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { downloadProjectFile, fetchProjectFileBlob, fetchProjectFileContent, saveProjectFileContent } from "../api";
import { htmlFileSrcDoc } from "../apiWindows";
import { ARTIFACT_IFRAME_SANDBOX } from "../artifactHtmlSecurity";
import { useI18n } from "../i18n";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import type { ProjectFileEntry } from "../types";
import { MarkdownText } from "./AgentRecordMarkdown";
import { UiIcon } from "./UiIcon";
import {
  ROOT_PATH,
  errorMessage,
  isBinaryPreviewError,
  isHtml,
  isImage,
  isMarkdown
} from "./projectFilesUtils";

export function ProjectFilePreviewPanel({
  browseRoot,
  clientId,
  projectPath,
  entry,
  targetLine = null,
  mode,
  onModeChange
}: {
  browseRoot?: string | null;
  clientId: string | null;
  projectPath: string | null;
  entry: ProjectFileEntry | null;
  targetLine?: number | null;
  mode: "edit" | "preview";
  onModeChange: (mode: "edit" | "preview") => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const selectedFilePath = entry?.kind === "file" ? entry.path : null;
  const isImageFile = isImage(selectedFilePath ?? "");
  const contentQuery = useQuery({
    queryKey: ["project-file-content", clientId, projectPath, browseRoot ?? null, selectedFilePath],
    queryFn: () => fetchProjectFileContent(
      clientId as string,
      projectPath as string,
      selectedFilePath as string,
      browseRoot
    ),
    enabled: clientId !== null
      && projectPath !== null
      && selectedFilePath !== null
      && !isImageFile,
    meta: { suppressApiErrorToast: true },
    retry: (failureCount, error) => !isBinaryPreviewError(error) && failureCount < 2,
    staleTime: 10000
  });
  const saveMutation = useMutation({
    mutationFn: (content: string) => saveProjectFileContent(
      clientId as string,
      projectPath as string,
      selectedFilePath as string,
      content,
      true,
      browseRoot
    ),
    onSuccess: (_result, content) => {
      queryClient.setQueryData(
        ["project-file-content", clientId, projectPath, browseRoot ?? null, selectedFilePath],
        {
          project_path: projectPath,
          path: selectedFilePath,
          content,
          encoding: "utf-8",
          truncated: false,
          size: new Blob([content]).size
        }
      );
      const directory = selectedFilePath?.includes("/")
        ? selectedFilePath.slice(0, selectedFilePath.lastIndexOf("/"))
        : ROOT_PATH;
      queryClient.invalidateQueries({ queryKey: ["project-files", clientId, projectPath, browseRoot ?? null, directory] });
      setSaveError(null);
      onModeChange("preview");
    },
    onError: (error) => setSaveError(errorMessage(error, t("projectFiles.saveFailed")))
  });
  const canDownload = clientId !== null && projectPath !== null && selectedFilePath !== null;
  const markdownProjectFileContext = useMemo<ProjectFileLinkContext | null>(() => {
    if (selectedFilePath === null || projectPath === null) {
      return null;
    }
    return {
      clientId,
      windowId: null,
      projectPath,
      browseRoot: browseRoot ?? null,
      cwd: projectFilePreviewCwd(projectPath, browseRoot, selectedFilePath)
    };
  }, [browseRoot, clientId, projectPath, selectedFilePath]);
  const isBinary = isBinaryPreviewError(contentQuery.error);
  const hasUnsavedChanges = mode === "edit" && contentQuery.data !== undefined && draft !== contentQuery.data.content;
  const htmlSrcDoc = useMemo(() => {
    if (contentQuery.data === undefined || !isHtml(selectedFilePath ?? "")) {
      return null;
    }
    return htmlFileSrcDoc(contentQuery.data.content);
  }, [contentQuery.data, selectedFilePath]);
  const imageBlobQuery = useQuery({
    queryKey: ["project-file-image", clientId, projectPath, browseRoot ?? null, selectedFilePath],
    queryFn: () => fetchProjectFileBlob(
      clientId as string,
      projectPath as string,
      selectedFilePath as string,
      browseRoot
    ),
    enabled: clientId !== null
      && projectPath !== null
      && selectedFilePath !== null
      && isImageFile,
    meta: { suppressApiErrorToast: true },
    retry: false,
    staleTime: 10000
  });
  const imageUrl = useMemo(() => {
    if (imageBlobQuery.data === undefined) {
      return null;
    }
    return URL.createObjectURL(imageBlobQuery.data);
  }, [imageBlobQuery.data]);
  const imageError = imageBlobQuery.isError
    ? errorMessage(imageBlobQuery.error, t("projectFiles.imageLoadFailed"))
    : null;

  useEffect(() => {
    if (imageUrl === null) {
      return;
    }
    return () => {
      URL.revokeObjectURL(imageUrl);
    };
  }, [imageUrl]);

  useEffect(() => {
    onModeChange("preview");
    setSaveError(null);
    setDraft("");
  }, [browseRoot, clientId, projectPath, selectedFilePath]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (contentQuery.data !== undefined) {
      setDraft(contentQuery.data.content);
    }
  }, [contentQuery.data]);

  useEffect(() => {
    if (mode === "edit" && contentQuery.data !== undefined) {
      setDraft(contentQuery.data.content);
      setSaveError(null);
    }
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  const startDownload = () => {
    if (clientId === null || projectPath === null || selectedFilePath === null) {
      return;
    }
    void downloadProjectFile(clientId, projectPath, selectedFilePath, browseRoot)
      .catch((error) => setSaveError(errorMessage(error, t("projectFiles.downloadFailed"))));
  };

  if (clientId === null || projectPath === null) {
    return (
      <section className="project-file-preview full" aria-label={t("projectFiles.previewLabel")}>
        <div className="project-file-preview-empty">
          <strong>{t("projectFiles.noProjectSelected")}</strong>
          <span>{t("projectFiles.selectProjectHelp")}</span>
        </div>
      </section>
    );
  }

  if (entry === null) {
    return (
      <section className="project-file-preview full" aria-label={t("projectFiles.previewLabel")}>
        <div className="project-file-preview-empty">
          <strong>{projectPath}</strong>
          <span>{t("projectFiles.selectFile")}</span>
        </div>
      </section>
    );
  }

  if (entry.kind === "directory") {
    return (
      <section className="project-file-preview full" aria-label={t("projectFiles.previewLabel")}>
        <div className="project-file-preview-empty">
          <strong>{entry.name}</strong>
          <span>{entry.path}</span>
        </div>
      </section>
    );
  }

  if (isImageFile) {
    return (
      <section className="project-file-preview full" aria-label={t("projectFiles.previewLabel")}>
        <div className="project-file-preview-document">
          {imageBlobQuery.isLoading && <p className="muted">{t("projectFiles.loadingPreview")}</p>}
          {imageError !== null && (
            <p className="error project-file-preview-save-error" role="alert">{imageError}</p>
          )}
          {imageUrl !== null && (
            <div className="image-preview">
              <img
                src={imageUrl}
                alt={entry.path}
              />
              {canDownload && (
                <button
                  type="button"
                  className="ui-icon-button image-preview-download"
                  aria-label={t("projectFiles.downloadNamed", { name: entry.name })}
                  title={t("common.download")}
                  onClick={startDownload}
                >
                  <UiIcon name="download" />
                </button>
              )}
            </div>
          )}
        </div>
      </section>
    );
  }

  if (isBinary) {
    return (
      <section className="project-file-preview full" aria-label={t("projectFiles.previewLabel")}>
        <div className="project-file-preview-empty">
          <strong>{entry.name}</strong>
          <span>{t("projectFiles.binaryUnavailable")}</span>
          {canDownload && (
            <button
              type="button"
              className="ui-icon-button"
              aria-label={t("projectFiles.downloadNamed", { name: entry.name })}
              title={t("common.download")}
              onClick={startDownload}
            >
              <UiIcon name="download" />
            </button>
          )}
          {saveError !== null && <p className="error" role="alert">{saveError}</p>}
        </div>
      </section>
    );
  }

  return (
    <section className="project-file-preview full" aria-label={t("projectFiles.previewLabel")}>
      <div className="project-file-preview-document">
        {contentQuery.isLoading && <p className="muted">{t("projectFiles.loadingPreview")}</p>}
        {contentQuery.isError && !isBinary && <p className="error" role="alert">{t("projectFiles.previewFailed")}</p>}
        {contentQuery.data?.truncated && (
          <p className="muted project-file-preview-truncated">{t("projectFiles.truncated")}</p>
        )}
        {saveError !== null && <p className="error project-file-preview-save-error" role="alert">{saveError}</p>}
        {mode === "edit" && contentQuery.data ? (
          <>
            <textarea
              className="text-file-editor"
              aria-label={t("projectFiles.editPath", { path: entry.path })}
              spellCheck={false}
              value={draft}
              onChange={(event) => setDraft(event.currentTarget.value)}
            />
            <div className="project-file-editor-actions">
              <button
                type="button"
                className="ui-icon-button"
                disabled={saveMutation.isPending || !hasUnsavedChanges}
                aria-label={t("projectFiles.savePath", { path: entry.path })}
                title={saveMutation.isPending ? t("common.saving") : t("common.save")}
                onClick={() => saveMutation.mutate(draft)}
              >
                <UiIcon name="save" />
              </button>
              <button
                type="button"
                className="ui-icon-button"
                disabled={saveMutation.isPending}
                aria-label={t("projectFiles.cancelEdit")}
                title={t("common.cancel")}
                onClick={() => {
                  setDraft(contentQuery.data.content);
                  onModeChange("preview");
                  setSaveError(null);
                }}
              >
                <UiIcon name="x" />
              </button>
            </div>
          </>
        ) : contentQuery.data && isMarkdown(entry.path) ? (
          <article className="markdown-preview">
            <MarkdownText text={contentQuery.data.content} projectFileContext={markdownProjectFileContext} />
          </article>
        ) : htmlSrcDoc !== null ? (
          <div className="html-preview">
            <iframe
              title={entry.path}
              sandbox={ARTIFACT_IFRAME_SANDBOX}
              referrerPolicy="no-referrer"
              srcDoc={htmlSrcDoc}
            />
          </div>
        ) : contentQuery.data ? (
          <TextFilePreview content={contentQuery.data.content} targetLine={targetLine} />
        ) : null}
      </div>
    </section>
  );
}

function projectFilePreviewCwd(projectPath: string, browseRoot: string | null | undefined, filePath: string): string {
  const root = trimTrailingSlash(browseRoot ?? projectPath);
  const directory = filePath.includes("/") ? filePath.slice(0, filePath.lastIndexOf("/")) : "";
  return directory.length === 0 ? root : `${root}/${directory}`;
}

function trimTrailingSlash(value: string): string {
  return value.length > 1 ? value.replace(/\/+$/u, "") : value;
}

function TextFilePreview({
  content,
  targetLine
}: {
  content: string;
  targetLine: number | null;
}) {
  const previewRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    if (targetLine === null) {
      return;
    }
    const target = previewRef.current?.querySelector<HTMLElement>(`[data-line-number="${targetLine}"]`);
    if (typeof target?.scrollIntoView === "function") {
      target.scrollIntoView({ block: "center" });
    }
  }, [content, targetLine]);

  return (
    <pre ref={previewRef} className="text-file-preview">
      {content.split("\n").map((line, index) => {
        const lineNumber = index + 1;
        const lineClassName = lineNumber === targetLine
          ? "text-file-preview-line text-file-preview-line-highlight"
          : "text-file-preview-line";
        return (
          <span key={lineNumber} className={lineClassName} data-line-number={lineNumber}>
            {line}
          </span>
        );
      })}
    </pre>
  );
}
