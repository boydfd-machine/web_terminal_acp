import type { CSSProperties, MutableRefObject, PointerEvent as ReactPointerEvent } from "react";
import type { ITheme } from "@xterm/xterm";

import { auxTerminalWebSocketUrl } from "../api";
import { useI18n, type TranslateFn } from "../i18n";
import { TerminalPane, type TerminalPaneHandle } from "./TerminalPane";

type TerminalDrawerMode = "artifact" | "aux" | "terminal";
type AuxTerminalDrawerTab = "terminal" | "todo";

export type TerminalDrawerProps = {
  activeAuxTerminalTab: AuxTerminalDrawerTab;
  artifactTerminalStatus: string;
  artifactTerminalTitle: string;
  artifactTerminalWindowId: string | null;
  autoFocusAuxTerminal: boolean;
  auxTerminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  auxTerminalStarting: boolean;
  auxTerminalUnavailable: boolean;
  clientId: string;
  dragActive: boolean;
  layoutVersion: string;
  mode: TerminalDrawerMode;
  open: boolean;
  showAuxTerminalTabs: boolean;
  selectedWindowId: string;
  selectedWindowTitle: string | null;
  style: CSSProperties;
  terminalWindowClientId: string | null;
  terminalWindowId: string | null;
  terminalWindowPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalWindowProjectPath: string | null;
  terminalWindowTitle: string | null;
  terminalTheme?: ITheme;
  onClose: () => void;
  onOpenTerminalTab: (clientId: string, windowId: string, projectPath: string) => void;
  onSelectAuxTerminalTab: (tab: AuxTerminalDrawerTab) => void;
  onPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
};

export function TerminalDrawer({
  activeAuxTerminalTab,
  artifactTerminalStatus,
  artifactTerminalTitle,
  artifactTerminalWindowId,
  autoFocusAuxTerminal,
  auxTerminalPaneRef,
  auxTerminalStarting,
  auxTerminalUnavailable,
  clientId,
  dragActive,
  layoutVersion,
  mode,
  open,
  showAuxTerminalTabs,
  selectedWindowId,
  selectedWindowTitle,
  style,
  terminalWindowClientId,
  terminalWindowId,
  terminalWindowPaneRef,
  terminalWindowProjectPath,
  terminalWindowTitle,
  terminalTheme,
  onClose,
  onOpenTerminalTab,
  onSelectAuxTerminalTab,
  onPointerCancel,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: TerminalDrawerProps) {
  const { t } = useI18n();
  const title = terminalDrawerTitle({
    artifactTerminalTitle,
    artifactTerminalStatus,
    mode,
    selectedWindowId,
    selectedWindowTitle,
    t,
    terminalWindowId,
    terminalWindowTitle,
  });
  const canOpenTerminalTab = (
    mode === "terminal"
    && terminalWindowClientId !== null
    && terminalWindowId !== null
    && terminalWindowProjectPath !== null
  );
  const showTodoTerminalPane = (
    open
    && mode === "terminal"
    && terminalWindowClientId !== null
    && terminalWindowId !== null
  );

  return (
    <section
      className="aux-terminal-drawer"
      role="dialog"
      aria-label={terminalDrawerAriaLabel(mode, t)}
      aria-hidden={!open}
      data-mode={mode}
      data-open={open ? "true" : "false"}
      data-dragging={dragActive ? "true" : "false"}
      style={style}
    >
      <div
        className="aux-terminal-header"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
      >
        <div className="aux-terminal-title">
          <strong>{title.heading}</strong>
          <span>{title.subtitle}</span>
        </div>
        {showAuxTerminalTabs && (
          <div className="aux-terminal-tabs" role="tablist" aria-label={t("terminal.drawer.tabs")}>
            <button
              type="button"
              role="tab"
              className={activeAuxTerminalTab === "terminal" ? "selected" : ""}
              aria-selected={activeAuxTerminalTab === "terminal"}
              onClick={() => onSelectAuxTerminalTab("terminal")}
            >
              {t("terminal.drawer.terminalAuxTab")}
            </button>
            <button
              type="button"
              role="tab"
              className={activeAuxTerminalTab === "todo" ? "selected" : ""}
              aria-selected={activeAuxTerminalTab === "todo"}
              onClick={() => onSelectAuxTerminalTab("todo")}
            >
              {t("terminal.drawer.todoAuxTab")}
            </button>
          </div>
        )}
        <div className="aux-terminal-header-actions">
          {mode === "terminal" ? (
            <button
              type="button"
              className="aux-terminal-icon-button"
              aria-label={t("terminal.drawer.openTab")}
              title={t("terminal.drawer.openTab")}
              disabled={!canOpenTerminalTab}
              onClick={() => {
                if (terminalWindowClientId !== null && terminalWindowId !== null && terminalWindowProjectPath !== null) {
                  onOpenTerminalTab(terminalWindowClientId, terminalWindowId, terminalWindowProjectPath);
                }
              }}
            >
              <OpenTerminalTabIcon />
            </button>
          ) : mode === "artifact" ? (
            <span role="status">
              {artifactTerminalStatus}
            </span>
          ) : (
            <>
              {auxTerminalStarting && <span role="status">{t("terminal.drawer.starting")}</span>}
              {auxTerminalUnavailable && <span role="alert">{t("terminal.drawer.unavailable")}</span>}
            </>
          )}
          <button type="button" onClick={onClose}>
            {mode === "artifact" ? t("terminal.drawer.hide") : t("terminal.drawer.close")}
          </button>
        </div>
      </div>
      <div className="aux-terminal-body">
        {showTodoTerminalPane && (
          <div className="aux-terminal-pane-slot">
            <TerminalPane
              ref={terminalWindowPaneRef}
              clientId={terminalWindowClientId as string}
              windowId={terminalWindowId as string}
              selectionEnabled={false}
              terminalSwitchingEnabled={true}
              priorityEnabled={false}
              autoFocus={open && mode === "terminal"}
              viewportMode="desktop"
              theme={terminalTheme}
              layoutVersion={layoutVersion}
            />
          </div>
        )}
        {mode === "terminal" ? (
          terminalWindowClientId === null || terminalWindowId === null ? (
            <div className="aux-terminal-placeholder" role="status">
              {t("terminal.drawer.preparing")}
            </div>
          ) : null
        ) : mode === "artifact" ? (
          artifactTerminalWindowId === null ? (
            <div className="aux-terminal-placeholder" role="status">
              {t("terminal.drawer.preparingArtifact")}
            </div>
          ) : (
            <TerminalPane
              key={`artifact-terminal-${clientId}-${artifactTerminalWindowId}`}
              ref={auxTerminalPaneRef}
              clientId={clientId}
              windowId={artifactTerminalWindowId}
              selectionEnabled={false}
              priorityEnabled={false}
              autoFocus={false}
              viewportMode="desktop"
              theme={terminalTheme}
              layoutVersion={layoutVersion}
            />
          )
        ) : (
          <TerminalPane
            key={`aux-terminal-${clientId}-${selectedWindowId}`}
            ref={auxTerminalPaneRef}
            clientId={clientId}
            windowId={selectedWindowId}
            webSocketUrl={auxTerminalWebSocketUrl}
            selectionEnabled={false}
            priorityEnabled={false}
            autoFocus={autoFocusAuxTerminal}
            viewportMode="desktop"
            theme={terminalTheme}
            layoutVersion={layoutVersion}
          />
        )}
      </div>
    </section>
  );
}

function terminalDrawerAriaLabel(mode: TerminalDrawerMode, t: TranslateFn): string {
  if (mode === "artifact") {
    return t("terminal.drawer.artifact");
  }
  if (mode === "terminal") {
    return t("terminal.drawer.terminal");
  }
  return t("terminal.drawer.aux");
}

function terminalDrawerTitle({
  artifactTerminalStatus,
  artifactTerminalTitle,
  mode,
  selectedWindowId,
  selectedWindowTitle,
  t,
  terminalWindowId,
  terminalWindowTitle,
}: {
  artifactTerminalStatus: string;
  artifactTerminalTitle: string;
  mode: TerminalDrawerMode;
  selectedWindowId: string;
  selectedWindowTitle: string | null;
  t: TranslateFn;
  terminalWindowId: string | null;
  terminalWindowTitle: string | null;
}): { heading: string; subtitle: string } {
  if (mode === "artifact") {
    return { heading: t("terminal.drawer.artifact"), subtitle: artifactTerminalTitle || artifactTerminalStatus };
  }
  if (mode === "terminal") {
    return { heading: t("terminal.drawer.windowFallback"), subtitle: terminalWindowTitle ?? terminalWindowId ?? t("terminal.drawer.windowFallback") };
  }
  return { heading: t("terminal.drawer.aux"), subtitle: selectedWindowTitle ?? selectedWindowId };
}

function OpenTerminalTabIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 5h16v14H4z" />
      <path d="m9 10 3 3-3 3" />
      <path d="M14 16h3" />
      <path d="M14 8h4" />
      <path d="m16 6 2 2-2 2" />
    </svg>
  );
}
