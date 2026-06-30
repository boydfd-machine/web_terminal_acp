import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "../i18n";
import {
  projectFileSwitchCandidates,
  type ProjectFileTab,
  type ProjectFileTabsState,
} from "../projectFileTabs";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectFileSwitcherProps = {
  activeKey: string | null;
  clientId: string | null;
  isOpen: boolean;
  tabsState: ProjectFileTabsState;
  onClose: () => void;
  onSelectTab: (tab: ProjectFileTab) => void;
};

export function ProjectFileSwitcher({
  activeKey,
  clientId,
  isOpen,
  tabsState,
  onClose,
  onSelectTab,
}: ProjectFileSwitcherProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [activeCandidateKey, setActiveCandidateKey] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const candidates = useMemo(
    () => projectFileSwitchCandidates(tabsState, clientId, query),
    [clientId, query, tabsState]
  );
  const candidateKeys = useMemo(() => candidates.map((candidate) => candidate.key), [candidates]);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      setActiveCandidateKey(null);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setActiveCandidateKey((currentKey) => {
      if (currentKey !== null && candidateKeys.includes(currentKey)) {
        return currentKey;
      }
      if (activeKey !== null && candidateKeys.includes(activeKey)) {
        return activeKey;
      }
      return candidateKeys[0] ?? null;
    });
  }, [activeKey, candidateKeys, isOpen]);

  const selectTab = useCallback((tab: ProjectFileTab) => {
    onSelectTab(tab);
    onClose();
  }, [onClose, onSelectTab]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (candidateKeys.length === 0) {
        return;
      }
      const activeIndex = activeCandidateKey === null ? -1 : candidateKeys.indexOf(activeCandidateKey);

      if (event.key === "ArrowDown") {
        event.preventDefault();
        const nextIndex = activeIndex < 0 ? 0 : (activeIndex + 1) % candidateKeys.length;
        setActiveCandidateKey(candidateKeys[nextIndex]);
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        const nextIndex = activeIndex < 0
          ? candidateKeys.length - 1
          : (activeIndex - 1 + candidateKeys.length) % candidateKeys.length;
        setActiveCandidateKey(candidateKeys[nextIndex]);
        return;
      }

      if (event.key === "Enter" && activeCandidateKey !== null) {
        const candidate = candidates.find((item) => item.key === activeCandidateKey);
        if (candidate === undefined) {
          return;
        }
        event.preventDefault();
        selectTab(candidate);
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [activeCandidateKey, candidateKeys, candidates, isOpen, selectTab]);

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: onClose,
    initialFocusSelector: "input"
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="project-file-switcher-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div ref={panelRef} aria-modal="true" className="project-file-switcher" role="dialog">
        <div className="project-file-switcher-header">
          <div>
            <h2>{t("projectFiles.switcher.title")}</h2>
            <p className="muted">{t("projectFiles.switcher.hint")}</p>
          </div>
          <button type="button" className="ui-icon-button" aria-label={t("common.close")} title={t("common.close")} onClick={onClose}>
            <UiIcon name="x" />
          </button>
        </div>

        <input
          aria-label={t("projectFiles.switcher.search")}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveCandidateKey(null);
          }}
          placeholder={t("projectFiles.switcher.search")}
        />

        {candidates.length === 0 ? (
          <p className="project-file-switcher-empty">{t("projectFiles.switcher.empty")}</p>
        ) : (
          <ul className="project-file-switcher-results" role="listbox" aria-label={t("projectFiles.switcher.title")}>
            {candidates.map((candidate) => {
              const active = candidate.key === activeCandidateKey;
              return (
                <li key={candidate.key}>
                  <button
                    type="button"
                    aria-current={candidate.active ? "true" : undefined}
                    aria-selected={active}
                    className={active ? "project-file-switcher-option active" : "project-file-switcher-option"}
                    onClick={() => selectTab(candidate)}
                    role="option"
                    title={`${candidate.projectPath}/${candidate.path}`}
                  >
                    <UiIcon name="file" />
                    <span className="project-file-switcher-main">
                      <strong>{candidate.name}</strong>
                      <span>{candidate.path}</span>
                    </span>
                    <span className="project-file-switcher-project">{candidate.projectPath}</span>
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
