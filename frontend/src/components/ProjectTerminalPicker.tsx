import { useEffect, useMemo, useRef, useState } from "react";

import type { ProjectSummary } from "../types";
import { projectGroupLabel } from "../terminalGrouping";

type ProjectTerminalPickerProps = {
  isOpen: boolean;
  projectPaths: string[];
  projectSummaries: ProjectSummary[];
  loadingProjects?: boolean;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
  onClose: () => void;
  onCreateTerminal: (projectPath: string) => void;
};

type ProjectOption = {
  path: string;
  label: string;
};

export function ProjectTerminalPicker({
  isOpen,
  projectPaths,
  projectSummaries,
  loadingProjects,
  creatingTerminal,
  createTerminalDisabled,
  onClose,
  onCreateTerminal
}: ProjectTerminalPickerProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
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
      return;
    }

    requestAnimationFrame(() => inputRef.current?.focus());
  }, [isOpen]);

  useEffect(() => {
    setActiveIndex((currentIndex) => {
      if (filteredOptions.length === 0) {
        return 0;
      }

      return Math.min(currentIndex, filteredOptions.length - 1);
    });
  }, [filteredOptions.length]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (filteredOptions.length === 0) {
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
        onCreateTerminal(option.path);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    activeIndex,
    createTerminalDisabled,
    creatingTerminal,
    filteredOptions,
    isOpen,
    onClose,
    onCreateTerminal
  ]);

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
      <div aria-modal="true" className="project-terminal-picker" role="dialog">
        <div className="project-terminal-picker-header">
          <div>
            <h2>New terminal by project path</h2>
            <p className="muted">Shift+Alt+N 选择现有项目路径新建 terminal</p>
          </div>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>

        <input
          ref={inputRef}
          aria-label="Search project paths"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
          }}
          placeholder="Search project path..."
        />

        {loadingProjects && projectPaths.length === 0 && (
          <p className="project-terminal-picker-empty">Loading project paths...</p>
        )}
        {!loadingProjects && projectPaths.length === 0 && (
          <p className="project-terminal-picker-empty">No project paths found for this client.</p>
        )}
        {!loadingProjects && projectPaths.length > 0 && filteredOptions.length === 0 && (
          <p className="project-terminal-picker-empty">No matching project paths.</p>
        )}
        {filteredOptions.length > 0 && (
          <ul className="project-terminal-picker-results" role="listbox" aria-label="Project paths">
            {filteredOptions.map((option, index) => {
              const isActive = index === activeIndex;

              return (
                <li key={option.path}>
                  <button
                    type="button"
                    aria-selected={isActive}
                    className={isActive ? "project-terminal-picker-option active" : "project-terminal-picker-option"}
                    disabled={creatingTerminal || createTerminalDisabled}
                    onClick={() => {
                      if (creatingTerminal || createTerminalDisabled) {
                        return;
                      }

                      onCreateTerminal(option.path);
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
