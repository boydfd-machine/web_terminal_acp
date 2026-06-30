import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { fetchProjectArtifactHtml, fetchTerminalArtifactHtml } from "../api";
import { isActiveTerminalArtifact } from "../artifactTerminalCarrier";
import { useI18n, type TranslateFn } from "../i18n";
import type { TerminalArtifact } from "../types";
import { ArtifactProjectTodoFrame } from "./ArtifactProjectTodoFrame";
import { UiIcon } from "./UiIcon";
import { useArtifactProjectTodoCreator } from "./useArtifactProjectTodoCreator";

type ArtifactQuickOpenMode = "terminal" | "result";

type ArtifactQuickOpenProps = {
  isOpen: boolean;
  artifacts: TerminalArtifact[];
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
  onOpenTerminal: (artifact: TerminalArtifact) => void;
  onOpenResult: (artifact: TerminalArtifact) => void;
};

type ArtifactResultViewerProps = {
  clientId: string;
  windowId: string;
  artifact: TerminalArtifact;
  projectPath: string | null;
  onClose: () => void;
};

function artifactStatusLabel(artifact: TerminalArtifact, t: TranslateFn): string {
  switch (artifact.status.toUpperCase()) {
    case "PENDING":
      return t("artifacts.status.pending");
    case "RUNNING":
      return t("artifacts.status.running");
    case "SUCCEEDED":
      return t("artifacts.status.ready");
    case "FAILED":
      return t("artifacts.status.failed");
    default:
      return artifact.status.toLowerCase();
  }
}

function artifactKindLabel(kind: string, t: TranslateFn): string {
  if (kind === "page_review_cards") {
    return t("artifacts.kind.pageReviewCards");
  }
  return kind
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function clampIndex(index: number, length: number): number {
  if (length <= 0) {
    return 0;
  }
  return Math.min(Math.max(index, 0), length - 1);
}

export function ArtifactQuickOpen({
  isOpen,
  artifacts,
  isLoading,
  isError,
  onClose,
  onOpenTerminal,
  onOpenResult
}: ArtifactQuickOpenProps) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLElement | null>(null);
  const terminalArtifacts = useMemo(
    () => artifacts.filter(isActiveTerminalArtifact),
    [artifacts]
  );
  const resultArtifacts = useMemo(
    () => artifacts.filter((artifact) => artifact.status.toUpperCase() === "SUCCEEDED"),
    [artifacts]
  );
  const [mode, setMode] = useState<ArtifactQuickOpenMode>("terminal");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const options = mode === "terminal" ? terminalArtifacts : resultArtifacts;

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setMode(terminalArtifacts.length > 0 ? "terminal" : "result");
    setSelectedIndex(0);
    window.requestAnimationFrame(() => dialogRef.current?.focus());
  }, [isOpen, terminalArtifacts.length]);

  useEffect(() => {
    setSelectedIndex((current) => clampIndex(current, options.length));
  }, [options.length]);

  if (!isOpen) {
    return null;
  }

  const openSelected = () => {
    const artifact = options[selectedIndex];
    if (artifact === undefined) {
      return;
    }
    if (mode === "terminal") {
      onOpenTerminal(artifact);
    } else {
      onOpenResult(artifact);
    }
  };

  return (
    <div className="artifact-quick-open-backdrop">
      <section
        ref={dialogRef}
        className="artifact-quick-open"
        role="dialog"
        aria-modal="true"
        aria-label={t("artifacts.quickOpen")}
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
            return;
          }
          if (event.key === "Tab") {
            event.preventDefault();
            setMode((current) => (current === "terminal" ? "result" : "terminal"));
            setSelectedIndex(0);
            return;
          }
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setSelectedIndex((current) => clampIndex(current + 1, options.length));
            return;
          }
          if (event.key === "ArrowUp") {
            event.preventDefault();
            setSelectedIndex((current) => clampIndex(current - 1, options.length));
            return;
          }
          if (event.key === "Enter") {
            event.preventDefault();
            openSelected();
          }
        }}
      >
        <header>
          <strong>{t("artifacts.quickOpen")}</strong>
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("common.close")}
            title={t("common.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        <div className="artifact-quick-tabs" role="tablist" aria-label={t("artifacts.view")}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "terminal"}
            className={mode === "terminal" ? "selected" : undefined}
            onClick={() => {
              setMode("terminal");
              setSelectedIndex(0);
            }}
          >
            {t("artifacts.scope.terminal")}
            <span>{terminalArtifacts.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "result"}
            className={mode === "result" ? "selected" : undefined}
            onClick={() => {
              setMode("result");
              setSelectedIndex(0);
            }}
          >
            {t("artifacts.result")}
            <span>{resultArtifacts.length}</span>
          </button>
        </div>
        {isLoading ? (
          <p className="artifact-quick-message">{t("artifacts.loading")}</p>
        ) : isError ? (
          <p className="artifact-quick-message error" role="alert">{t("artifacts.loadFailed")}</p>
        ) : options.length === 0 ? (
          <p className="artifact-quick-message">
            {mode === "terminal"
              ? t("artifacts.noActiveTerminalArtifacts")
              : t("artifacts.noFinishedResults")}
          </p>
        ) : (
          <div className="artifact-quick-list" role="listbox" aria-label={`${mode === "terminal" ? t("artifacts.scope.terminal") : t("artifacts.result")} ${t("artifacts.title")}`}>
            {options.map((artifact, index) => (
              <button
                key={artifact.id}
                type="button"
                role="option"
                aria-selected={index === selectedIndex}
                className={index === selectedIndex ? "selected" : undefined}
                onMouseEnter={() => setSelectedIndex(index)}
                onClick={() => {
                  if (mode === "terminal") {
                    onOpenTerminal(artifact);
                  } else {
                    onOpenResult(artifact);
                  }
                }}
              >
                <strong>{artifact.title}</strong>
                <span>{artifactKindLabel(artifact.artifact_kind, t)}</span>
                <small className={`artifact-status ${artifact.status.toLowerCase()}`}>
                  {artifactStatusLabel(artifact, t)}
                </small>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export function ArtifactResultViewer({
  clientId,
  windowId,
  artifact,
  projectPath,
  onClose
}: ArtifactResultViewerProps) {
  const { t } = useI18n();
  const createTodoFromArtifactMutation = useArtifactProjectTodoCreator();
  const htmlQuery = useQuery({
    queryKey: [
      "terminal-artifact-html",
      clientId,
      windowId,
      artifact.artifact_scope,
      artifact.project_path,
      artifact.id,
      artifact.updated_at
    ],
    queryFn: () => {
      if (artifact.artifact_scope === "project" && artifact.project_path !== null) {
        return fetchProjectArtifactHtml(clientId, artifact.project_path, artifact.id);
      }
      return fetchTerminalArtifactHtml(clientId, windowId, artifact.id);
    },
    enabled: artifact.status.toUpperCase() === "SUCCEEDED",
    staleTime: Infinity
  });
  const srcDoc = htmlQuery.data ?? null;
  const targetProjectPath = artifact.project_path ?? projectPath;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      onClose();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="artifact-fullscreen" role="dialog" aria-modal="true" aria-label={t("artifacts.terminalArtifact")}>
      <button
        type="button"
        className="artifact-fullscreen-backdrop"
        aria-label={t("artifacts.closeArtifact")}
        onClick={onClose}
      />
      <section className="artifact-fullscreen-panel">
        <header>
          <strong>{artifact.title}</strong>
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("artifacts.closeArtifact")}
            title={t("common.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        {htmlQuery.isError ? (
          <p className="artifact-fullscreen-message error" role="alert">{t("artifacts.previewFailed")}</p>
        ) : srcDoc === null ? (
          <p className="artifact-fullscreen-message">{t("artifacts.previewLoading")}</p>
        ) : (
          <ArtifactProjectTodoFrame
            artifactId={artifact.id}
            clientId={clientId}
            projectPath={targetProjectPath}
            srcDoc={srcDoc}
            title={artifact.title}
            onCreateProjectTodo={(card, artifactId) => {
              if (targetProjectPath === null) {
                return Promise.reject(new Error("project path is required"));
              }
              return createTodoFromArtifactMutation.mutateAsync({
                artifactId,
                card,
                clientId,
                projectPath: targetProjectPath
              });
            }}
          />
        )}
      </section>
    </div>
  );
}
