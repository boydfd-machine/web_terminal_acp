import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DEFAULT_AGENT_CLIENTS,
  agentLaunchForClient,
  agentLaunchOptions,
  isAgentLaunchKind,
} from "../agentLaunch";
import type { AgentLaunchMode } from "../agentLaunch";
import { agentLaunchFromProjectPreference } from "../projectAgentPreference";
import type { AgentClient, AgentLaunchConfig, Project, ProjectSummary } from "../types";
import { useI18n } from "../i18n";
import { projectGroupLabel } from "../terminalGrouping";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectTerminalPickerProps = {
  isOpen: boolean;
  projectPaths: string[];
  projects?: Project[];
  projectSummaries: ProjectSummary[];
  agentClients?: AgentClient[];
  loadingProjects?: boolean;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
  onClose: () => void;
  onCreateTerminal: (projectPath: string, agentLaunch: AgentLaunchConfig | null) => void;
  onConfigureTerminal?: (projectPath: string, agentLaunch: AgentLaunchConfig) => void;
};

type ProjectOption = {
  path: string;
  label: string;
};

type ProjectTerminalLaunchMode = "project-default" | AgentLaunchMode;

export function ProjectTerminalPicker({
  isOpen,
  projectPaths,
  projects = [],
  projectSummaries,
  agentClients: agentClientsProp,
  loadingProjects,
  creatingTerminal,
  createTerminalDisabled,
  onClose,
  onCreateTerminal,
  onConfigureTerminal
}: ProjectTerminalPickerProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [selectedMode, setSelectedMode] = useState<ProjectTerminalLaunchMode>("project-default");
  const panelRef = useRef<HTMLDivElement | null>(null);
  const agentClients = agentClientsProp ?? DEFAULT_AGENT_CLIENTS;
  const launchOptions = useMemo(
    () => [
      { id: "project-default" as const, label: t("projectTerminal.projectDefault") },
      ...agentLaunchOptions(agentClients)
    ],
    [agentClients, t]
  );
  const projectSummaryLookup = useMemo(() => {
    const lookup = new Map<string, ProjectSummary>();
    for (const summary of projectSummaries) {
      lookup.set(summary.project_path, summary);
    }
    return lookup;
  }, [projectSummaries]);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const options = useMemo<ProjectOption[]>(
    () => projectPaths.map((path) => ({
      path,
      label: projectGroupLabel(path, projectSummaryLookup)
    })),
    [projectPaths, projectSummaryLookup]
  );
  const filteredOptions = useMemo(
    () => options.filter((option) => {
      if (!normalizedQuery) {
        return true;
      }

      return `${option.label} ${option.path}`.toLocaleLowerCase().includes(normalizedQuery);
    }),
    [normalizedQuery, options]
  );

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      setActiveIndex(0);
      setSelectedMode("project-default");
    }
  }, [isOpen]);

  useEffect(() => {
    setActiveIndex((currentIndex) => {
      if (filteredOptions.length === 0) {
        return 0;
      }

      return Math.min(currentIndex, filteredOptions.length - 1);
    });
  }, [filteredOptions.length]);

  const activeOption = filteredOptions[activeIndex] ?? null;
  const projectPreferencesByPath = useMemo(() => {
    const lookup = new Map<string, Project["agent_preference"]>();
    for (const project of projects) {
      lookup.set(project.path, project.agent_preference ?? null);
    }
    return lookup;
  }, [projects]);
  const agentLaunchForSelection = useCallback((projectPath: string): AgentLaunchConfig | null => {
    if (selectedMode === "project-default") {
      return agentLaunchFromProjectPreference(projectPreferencesByPath.get(projectPath), agentClients);
    }
    if (selectedMode !== "project-default" && isAgentLaunchKind(selectedMode)) {
      return agentLaunchForClient(selectedMode, agentClients);
    }
    return null;
  }, [agentClients, projectPreferencesByPath, selectedMode]);
  const createTerminalForProject = useCallback((projectPath: string) => {
    onCreateTerminal(projectPath, agentLaunchForSelection(projectPath));
  }, [agentLaunchForSelection, onCreateTerminal]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (filteredOptions.length === 0) {
        return;
      }

      if (event.key === "Tab") {
        event.preventDefault();
        setSelectedMode((currentMode) => {
          const currentIndex = launchOptions.findIndex((option) => option.id === currentMode);
          const offset = event.shiftKey ? -1 : 1;
          const nextIndex = (currentIndex + offset + launchOptions.length) % launchOptions.length;
          return launchOptions[nextIndex].id;
        });
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((currentIndex) => (currentIndex + 1) % filteredOptions.length);
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((currentIndex) => (currentIndex - 1 + filteredOptions.length) % filteredOptions.length);
        return;
      }

      if (event.key === "Enter") {
        const option = filteredOptions[activeIndex];
        if (!option || creatingTerminal || createTerminalDisabled) {
          return;
        }

        event.preventDefault();
        createTerminalForProject(option.path);
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [
    activeIndex,
    createTerminalDisabled,
    creatingTerminal,
    filteredOptions,
    isOpen,
    createTerminalForProject,
    launchOptions
  ]);

  const handleEscape = useCallback(() => {
    onClose();
  }, [onClose]);

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: handleEscape,
    initialFocusSelector: "input"
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="project-terminal-picker-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div ref={panelRef} aria-modal="true" className="project-terminal-picker" role="dialog">
        <div className="project-terminal-picker-header">
          <div>
            <h2>{t("projectTerminal.title")}</h2>
            <p className="muted">{t("projectTerminal.description")}</p>
          </div>
          <div className="project-terminal-picker-actions">
            {onConfigureTerminal && (
              <button
                type="button"
                disabled={
                  activeOption === null
                  || agentLaunchForSelection(activeOption.path) === null
                  || creatingTerminal
                  || createTerminalDisabled
                }
                onClick={() => {
                  if (activeOption !== null) {
                    const agentLaunch = agentLaunchForSelection(activeOption.path);
                    if (agentLaunch !== null) {
                      onConfigureTerminal(activeOption.path, agentLaunch);
                    }
                  }
                }}
              >
                {t("projectTerminal.configure")}
              </button>
            )}
            <button type="button" onClick={onClose}>
              {t("common.close")}
            </button>
          </div>
        </div>

        <div className="project-terminal-picker-agent-tabs" role="tablist" aria-label={t("projectTerminal.agentTabs")}>
          {launchOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              className={selectedMode === option.id ? "active" : undefined}
              aria-selected={selectedMode === option.id}
              onClick={() => {
                setSelectedMode(option.id);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>

        <input
          aria-label={t("projectTerminal.search")}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
          }}
          placeholder={t("projectTerminal.searchPlaceholder")}
        />

        {loadingProjects && projectPaths.length === 0 && (
          <p className="project-terminal-picker-empty">{t("projectTerminal.loading")}</p>
        )}
        {!loadingProjects && projectPaths.length === 0 && (
          <p className="project-terminal-picker-empty">{t("projectTerminal.empty")}</p>
        )}
        {!loadingProjects && projectPaths.length > 0 && filteredOptions.length === 0 && (
          <p className="project-terminal-picker-empty">{t("projectTerminal.noMatch")}</p>
        )}
        {filteredOptions.length > 0 && (
          <ul className="project-terminal-picker-results" role="listbox" aria-label={t("projectTerminal.projectPaths")}>
            {filteredOptions.map((option, index) => {
              const isActive = index === activeIndex;

              return (
                <li key={option.path} className="project-terminal-picker-result">
                  <button
                    type="button"
                    aria-selected={isActive}
                    className={isActive ? "project-terminal-picker-option active" : "project-terminal-picker-option"}
                    disabled={creatingTerminal || createTerminalDisabled}
                    onClick={() => {
                      if (creatingTerminal || createTerminalDisabled) {
                        return;
                      }

                      createTerminalForProject(option.path);
                    }}
                    role="option"
                    title={option.path}
                  >
                    <span className="project-terminal-picker-label">{option.label}</span>
                    <span className="project-terminal-picker-path">{option.path}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
