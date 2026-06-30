import { useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "../i18n";
import type { ProjectBrowseRootOption } from "../projectBrowseRoots";

export function ProjectBrowseRootSelector({
  options,
  selectedBrowseRoot,
  selectedProjectPath,
  onSelect,
}: {
  options: ProjectBrowseRootOption[];
  selectedBrowseRoot: string | null;
  selectedProjectPath: string | null;
  onSelect: (option: ProjectBrowseRootOption) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selectedOption = useMemo(
    () => selectedBrowseRootOption(options, selectedProjectPath, selectedBrowseRoot),
    [options, selectedBrowseRoot, selectedProjectPath],
  );
  const filteredOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (normalizedQuery.length === 0) {
      return options;
    }
    return options.filter((option) => option.searchText.includes(normalizedQuery));
  }, [options, query]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) {
      setQuery("");
    }
  }, [open]);

  return (
    <div className="project-browse-root-selector" ref={rootRef}>
      <button
        type="button"
        className="project-browse-root-button"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={options.length === 0}
        title={selectedOption?.detail ?? selectedProjectPath ?? t("projectFiles.projectRoot")}
        onClick={() => setOpen((isOpen) => !isOpen)}
      >
        <span>{selectedOption?.label ?? t("projectFiles.projectRoot")}</span>
      </button>
      {open && (
        <div className="project-browse-root-menu">
          <input
            type="search"
            value={query}
            aria-label={t("projectFiles.searchWorktrees")}
            placeholder={t("projectFiles.searchWorktrees")}
            autoFocus
            onChange={(event) => setQuery(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setOpen(false);
              }
            }}
          />
          <div className="project-browse-root-options" role="listbox" aria-label={t("projectFiles.rootLabel")}>
            {filteredOptions.map((option) => {
              const selected = selectedOption?.id === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={selected ? "selected" : ""}
                  title={option.detail}
                  onClick={() => {
                    onSelect(option);
                    setOpen(false);
                  }}
                >
                  <span className="project-browse-root-option-main">
                    <strong>{option.label}</strong>
                    {option.pendingCommit && <span className="project-browse-root-pending">{t("projectFiles.pending")}</span>}
                  </span>
                  <span>{option.detail}</span>
                </button>
              );
            })}
            {filteredOptions.length === 0 && (
              <p className="muted project-browse-root-empty">{t("projectFiles.noWorktrees")}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function selectedBrowseRootOption(
  options: ProjectBrowseRootOption[],
  selectedProjectPath: string | null,
  selectedBrowseRoot: string | null,
): ProjectBrowseRootOption | null {
  return options.find((option) => (
    option.projectPath === selectedProjectPath
    && (option.browseRoot ?? null) === selectedBrowseRoot
  )) ?? options.find((option) => (option.browseRoot ?? null) === selectedBrowseRoot) ?? options[0] ?? null;
}
