import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { searchProjectFiles } from "../api";
import { useI18n } from "../i18n";
import { dispatchProjectFileOpenRequest } from "../projectFileLinks";
import type { ProjectFileSearchResponse, ProjectFileSearchResult } from "../types";
import { highlightedFieldText } from "./SearchHighlights";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

const PROJECT_FILE_SEARCH_PAGE_SIZE = 25;

type ProjectFileSearchModalProps = {
  clientId: string | null;
  isOpen: boolean;
  projectPath: string | null;
  selectedWindowId: string | null;
  onClose: () => void;
};

export function ProjectFileSearchModal({
  clientId,
  isOpen,
  projectPath,
  selectedWindowId,
  onClose,
}: ProjectFileSearchModalProps) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const panelRef = useRef<HTMLElement | null>(null);
  const submitted = query.trim();
  const canSearch = isOpen && clientId !== null && projectPath !== null && submitted.length > 0;
  const activeClientId = clientId ?? "";
  const activeProjectPath = projectPath ?? "";

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    initialFocusSelector: "#project-file-search-input",
    onEscape: onClose,
    preserveExistingFocus: true
  });

  useEffect(() => {
    if (!isOpen) {
      setDraft("");
      setQuery("");
      setPage(0);
    }
  }, [isOpen]);

  const searchQuery = useQuery({
    queryKey: [
      "project-file-search",
      clientId,
      projectPath,
      submitted,
      page,
      PROJECT_FILE_SEARCH_PAGE_SIZE,
    ],
    queryFn: () => searchProjectFiles(
      clientId as string,
      submitted,
      PROJECT_FILE_SEARCH_PAGE_SIZE,
      page * PROJECT_FILE_SEARCH_PAGE_SIZE,
      projectPath as string,
      "all"
    ),
    enabled: canSearch,
    placeholderData: keepPreviousData
  });

  const submit = useCallback((nextQuery: string) => {
    const trimmed = nextQuery.trim();
    setDraft(nextQuery);
    setQuery(trimmed);
    setPage(0);
  }, []);

  const openFileResult = useCallback((result: ProjectFileSearchResult) => {
    dispatchProjectFileOpenRequest({
      clientId: activeClientId,
      windowId: selectedWindowId,
      projectPath: result.project_path,
      browseRoot: null,
      path: result.path,
      line: result.line,
    });
    onClose();
  }, [activeClientId, onClose, selectedWindowId]);

  if (!isOpen) {
    return null;
  }

  const record = searchQuery.data ?? null;

  return (
    <div className="global-search-modal project-file-search-modal" role="dialog" aria-modal="true" aria-label={t("projectFiles.search.title")}>
      <button type="button" className="global-search-backdrop" aria-label={t("common.close")} onClick={onClose} />
      <section ref={panelRef} className="global-search-panel project-file-search-panel">
        <header>
          <div>
            <h2>{t("projectFiles.search.title")}</h2>
            <p>{projectPath === null ? t("projectFiles.search.selectProject") : t("projectFiles.search.subtitle", { project: activeProjectPath })}</p>
          </div>
          <button type="button" className="ui-icon-button" aria-label={t("common.close")} title={t("common.close")} onClick={onClose}>
            <UiIcon name="x" />
          </button>
        </header>
        <form
          className="global-search-form"
          onSubmit={(event) => {
            event.preventDefault();
            submit(draft);
          }}
        >
          <label htmlFor="project-file-search-input">{t("projectFiles.search.label")}</label>
          <div className="global-search-row">
            <input
              id="project-file-search-input"
              type="search"
              value={draft}
              placeholder={t("projectFiles.search.placeholder")}
              disabled={clientId === null || projectPath === null}
              autoFocus
              onChange={(event) => setDraft(event.target.value)}
            />
            <button
              type="submit"
              className="ui-icon-button"
              disabled={clientId === null || projectPath === null}
              aria-label={t("globalSearch.submit")}
              title={t("globalSearch.submit")}
            >
              <UiIcon name="search" />
            </button>
          </div>
        </form>
        <div className="global-search-results">
          {clientId === null || projectPath === null || submitted.length === 0 ? (
            <p className="muted">
              {clientId === null || projectPath === null ? t("projectFiles.search.selectProject") : t("globalSearch.emptyQuery")}
            </p>
          ) : (
            <ProjectFileSearchResults
              record={record}
              isLoading={searchQuery.isLoading}
              isError={searchQuery.isError}
              isFetching={searchQuery.isFetching}
              onNextPage={() => setPage((currentPage) => currentPage + 1)}
              onOpenFile={openFileResult}
              onPreviousPage={() => setPage((currentPage) => Math.max(0, currentPage - 1))}
            />
          )}
        </div>
      </section>
    </div>
  );
}

function ProjectFileSearchResults({
  record,
  isLoading,
  isError,
  isFetching,
  onNextPage,
  onOpenFile,
  onPreviousPage,
}: {
  record: ProjectFileSearchResponse | null;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  onNextPage: () => void;
  onOpenFile: (result: ProjectFileSearchResult) => void;
  onPreviousPage: () => void;
}) {
  const { t } = useI18n();
  if (isLoading) {
    return <p className="muted">{t("globalSearch.searching")}</p>;
  }
  if (isError) {
    return <p className="error" role="alert">{t("globalSearch.failed")}</p>;
  }
  if (record === null) {
    return null;
  }

  return (
    <>
      <div className="global-search-meta">
        <ProjectFileSearchResultMeta
          count={record.results.length}
          isFetching={isFetching}
          offset={record.offset}
          total={record.total}
        />
        <div>
          <button type="button" onClick={onPreviousPage} disabled={record.offset === 0}>{t("common.previous")}</button>
          <button type="button" onClick={onNextPage} disabled={!record.has_more}>{t("common.next")}</button>
        </div>
      </div>
      {record.truncated && (
        <p className="global-search-note">{t("globalSearch.filesTruncated", { count: record.scanned_files })}</p>
      )}
      <div className="global-file-results">
        {record.results.map((result, index) => (
          <ProjectFileSearchResultCard
            key={`${result.project_path}:${result.path}:${result.line ?? "path"}:${index}`}
            result={result}
            onOpenFile={onOpenFile}
          />
        ))}
      </div>
    </>
  );
}

function ProjectFileSearchResultCard({
  result,
  onOpenFile,
}: {
  result: ProjectFileSearchResult;
  onOpenFile: (result: ProjectFileSearchResult) => void;
}) {
  const { t } = useI18n();
  return (
    <article className="global-file-result">
      <header>
        <div>
          <span>{result.project_path}</span>
          <strong>
            {highlightedFieldText(result.path, result.matches, "path")}
            {result.line !== null ? `:${result.line}` : ""}
          </strong>
        </div>
      </header>
      <p>{highlightedFieldText(result.snippet, result.matches, "snippet")}</p>
      <footer>
        <span>{result.line === null ? t("globalSearch.filePathMatch") : t("globalSearch.fileLine", { line: result.line })}</span>
        <button type="button" onClick={() => onOpenFile(result)}>
          {t("globalSearch.openFile")}
        </button>
      </footer>
    </article>
  );
}

function ProjectFileSearchResultMeta({
  count,
  isFetching,
  offset,
  total,
}: {
  count: number;
  isFetching: boolean;
  offset: number;
  total: number;
}) {
  const { t } = useI18n();
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + count, total);
  return (
    <span>
      {total === 0
        ? t("globalSearch.noResults")
        : t("globalSearch.resultRange", { start, end, total })}
      {isFetching ? ` · ${t("agentRecord.refreshing")}` : ""}
    </span>
  );
}
