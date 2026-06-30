import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { searchAgentRecords, searchProjectFiles, searchProjectTodos } from "../api";
import { useI18n } from "../i18n";
import { dispatchProjectFileOpenRequest } from "../projectFileLinks";
import type {
  AgentRecordSearchResponse,
  ProjectFileSearchResponse,
  ProjectFileSearchResult,
  ProjectTodoSearchResponse,
  ProjectTodoSearchResult
} from "../types";
import { AgentChatMessageCard } from "./AgentRecordContent";
import { formatDateTime } from "./AgentRecordData";
import { highlightedFieldText } from "./SearchHighlights";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

const GLOBAL_SEARCH_PAGE_SIZE = 25;

type GlobalSearchType = "agent-record" | "kanban" | "file-content" | "filename";

export function GlobalSearchModal({
  clientId,
  open,
  onClose,
  onFocusProjectTodo,
  onSelectWindow
}: {
  clientId: string | null;
  open: boolean;
  onClose: () => void;
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
  onSelectWindow: (windowId: string, clientId?: string | null) => void;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [type, setType] = useState<GlobalSearchType>("agent-record");
  const [agentPage, setAgentPage] = useState(0);
  const [kanbanPage, setKanbanPage] = useState(0);
  const [fileContentPage, setFileContentPage] = useState(0);
  const [filenamePage, setFilenamePage] = useState(0);
  const panelRef = useRef<HTMLElement | null>(null);
  const submitted = query.trim();
  const active = open && clientId !== null && submitted.length > 0;
  const activeClientId = clientId ?? "";

  useOverlayFocus({
    isOpen: open,
    ref: panelRef,
    initialFocusSelector: "#global-search-input",
    onEscape: onClose,
    preserveExistingFocus: true
  });

  useEffect(() => {
    if (!open) {
      setDraft("");
      setQuery("");
      setType("agent-record");
      setAgentPage(0);
      setKanbanPage(0);
      setFileContentPage(0);
      setFilenamePage(0);
    }
  }, [open]);

  const agentQuery = useQuery({
    queryKey: ["global-search", "agent-record", clientId, submitted, agentPage, GLOBAL_SEARCH_PAGE_SIZE],
    queryFn: () => searchAgentRecords(
      clientId as string,
      submitted,
      GLOBAL_SEARCH_PAGE_SIZE,
      agentPage * GLOBAL_SEARCH_PAGE_SIZE
    ),
    enabled: active && type === "agent-record",
    placeholderData: keepPreviousData
  });
  const kanbanQuery = useQuery({
    queryKey: ["global-search", "kanban", clientId, submitted, kanbanPage, GLOBAL_SEARCH_PAGE_SIZE],
    queryFn: () => searchProjectTodos(
      clientId as string,
      submitted,
      GLOBAL_SEARCH_PAGE_SIZE,
      kanbanPage * GLOBAL_SEARCH_PAGE_SIZE
    ),
    enabled: active && type === "kanban",
    placeholderData: keepPreviousData
  });
  const fileContentQuery = useQuery({
    queryKey: ["global-search", "file-content", clientId, submitted, fileContentPage, GLOBAL_SEARCH_PAGE_SIZE],
    queryFn: () => searchProjectFiles(
      clientId as string,
      submitted,
      GLOBAL_SEARCH_PAGE_SIZE,
      fileContentPage * GLOBAL_SEARCH_PAGE_SIZE,
      undefined,
      "content"
    ),
    enabled: active && type === "file-content",
    placeholderData: keepPreviousData
  });
  const filenameQuery = useQuery({
    queryKey: ["global-search", "filename", clientId, submitted, filenamePage, GLOBAL_SEARCH_PAGE_SIZE],
    queryFn: () => searchProjectFiles(
      clientId as string,
      submitted,
      GLOBAL_SEARCH_PAGE_SIZE,
      filenamePage * GLOBAL_SEARCH_PAGE_SIZE,
      undefined,
      "filename"
    ),
    enabled: active && type === "filename",
    placeholderData: keepPreviousData
  });

  const submit = useCallback((nextQuery: string) => {
    const trimmed = nextQuery.trim();
    setDraft(nextQuery);
    setQuery(trimmed);
    setAgentPage(0);
    setKanbanPage(0);
    setFileContentPage(0);
    setFilenamePage(0);
  }, []);
  const openFileResult = useCallback((result: ProjectFileSearchResult) => {
    dispatchProjectFileOpenRequest({
      clientId: activeClientId,
      windowId: null,
      projectPath: result.project_path,
      browseRoot: null,
      path: result.path,
      line: result.line
    });
    onClose();
  }, [activeClientId, onClose]);

  const currentAgentRecord = agentQuery.data ?? null;
  const currentKanbanRecord = kanbanQuery.data ?? null;
  const currentFileContentRecord = fileContentQuery.data ?? null;
  const currentFilenameRecord = filenameQuery.data ?? null;

  if (!open) {
    return null;
  }

  return (
    <div className="global-search-modal" role="dialog" aria-modal="true" aria-label={t("globalSearch.title")}>
      <button type="button" className="global-search-backdrop" aria-label={t("common.close")} onClick={onClose} />
      <section ref={panelRef} className="global-search-panel">
        <header>
          <div>
            <h2>{t("globalSearch.title")}</h2>
            <p>{clientId === null ? t("globalSearch.selectClient") : t("globalSearch.subtitle")}</p>
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
          <label htmlFor="global-search-input">{t("globalSearch.label")}</label>
          <div className="global-search-row">
            <input
              id="global-search-input"
              type="search"
              value={draft}
              placeholder={t("globalSearch.placeholder")}
              disabled={clientId === null}
              autoFocus
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="submit" className="ui-icon-button" disabled={clientId === null} aria-label={t("globalSearch.submit")} title={t("globalSearch.submit")}>
              <UiIcon name="search" />
            </button>
          </div>
        </form>
        <div className="global-search-tabs" role="tablist" aria-label={t("globalSearch.type")}>
          <button type="button" role="tab" aria-selected={type === "agent-record"} className={type === "agent-record" ? "selected" : undefined} onClick={() => setType("agent-record")}>
            {t("globalSearch.type.agentRecord")}
          </button>
          <button type="button" role="tab" aria-selected={type === "kanban"} className={type === "kanban" ? "selected" : undefined} onClick={() => setType("kanban")}>
            {t("globalSearch.type.kanban")}
          </button>
          <button type="button" role="tab" aria-selected={type === "file-content"} className={type === "file-content" ? "selected" : undefined} onClick={() => setType("file-content")}>
            {t("globalSearch.type.fileContents")}
          </button>
          <button type="button" role="tab" aria-selected={type === "filename"} className={type === "filename" ? "selected" : undefined} onClick={() => setType("filename")}>
            {t("globalSearch.type.filenames")}
          </button>
        </div>
        <div className="global-search-results">
          {clientId === null || submitted.length === 0 ? (
            <p className="muted">{clientId === null ? t("globalSearch.selectClient") : t("globalSearch.emptyQuery")}</p>
          ) : type === "agent-record" ? (
            <GlobalAgentRecordResults
              record={currentAgentRecord}
              isLoading={agentQuery.isLoading}
              isError={agentQuery.isError}
              isFetching={agentQuery.isFetching}
              onNextPage={() => setAgentPage((page) => page + 1)}
              onPreviousPage={() => setAgentPage((page) => Math.max(0, page - 1))}
              onSelectWindow={(windowId) => {
                onSelectWindow(windowId, clientId);
                onClose();
              }}
            />
          ) : type === "kanban" ? (
            <GlobalKanbanResults
              record={currentKanbanRecord}
              isLoading={kanbanQuery.isLoading}
              isError={kanbanQuery.isError}
              isFetching={kanbanQuery.isFetching}
              onFocusProjectTodo={(projectPath, todoId) => {
                onFocusProjectTodo(projectPath, todoId);
                onClose();
              }}
              onNextPage={() => setKanbanPage((page) => page + 1)}
              onPreviousPage={() => setKanbanPage((page) => Math.max(0, page - 1))}
            />
          ) : type === "file-content" ? (
            <GlobalFileResults
              record={currentFileContentRecord}
              isLoading={fileContentQuery.isLoading}
              isError={fileContentQuery.isError}
              isFetching={fileContentQuery.isFetching}
              clientId={activeClientId}
              onOpenFile={openFileResult}
              onNextPage={() => setFileContentPage((page) => page + 1)}
              onPreviousPage={() => setFileContentPage((page) => Math.max(0, page - 1))}
            />
          ) : (
            <GlobalFileResults
              record={currentFilenameRecord}
              isLoading={filenameQuery.isLoading}
              isError={filenameQuery.isError}
              isFetching={filenameQuery.isFetching}
              clientId={activeClientId}
              onOpenFile={openFileResult}
              onNextPage={() => setFilenamePage((page) => page + 1)}
              onPreviousPage={() => setFilenamePage((page) => Math.max(0, page - 1))}
            />
          )}
        </div>
      </section>
    </div>
  );
}

function GlobalFileResults({
  record,
  isLoading,
  isError,
  isFetching,
  clientId,
  onOpenFile,
  onNextPage,
  onPreviousPage
}: {
  record: ProjectFileSearchResponse | null;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  clientId: string;
  onOpenFile: (result: ProjectFileSearchResult) => void;
  onNextPage: () => void;
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
        <ResultMeta count={record.results.length} isFetching={isFetching} limit={record.limit} offset={record.offset} total={record.total} />
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
          <FileSearchResultCard
            key={`${clientId}:${result.project_path}:${result.path}:${result.line ?? "path"}:${index}`}
            result={result}
            onOpenFile={onOpenFile}
          />
        ))}
      </div>
    </>
  );
}

function FileSearchResultCard({
  result,
  onOpenFile
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

function ResultMeta({
  count,
  isFetching,
  limit,
  offset,
  total
}: {
  count: number;
  isFetching: boolean;
  limit: number;
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

function GlobalAgentRecordResults({
  record,
  isLoading,
  isError,
  isFetching,
  onNextPage,
  onPreviousPage,
  onSelectWindow
}: {
  record: AgentRecordSearchResponse | null;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  onNextPage: () => void;
  onPreviousPage: () => void;
  onSelectWindow: (windowId: string) => void;
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
        <ResultMeta count={record.results.length} isFetching={isFetching} limit={record.limit} offset={record.offset} total={record.total} />
        <div>
          <button type="button" onClick={onPreviousPage} disabled={record.offset === 0}>{t("common.previous")}</button>
          <button type="button" onClick={onNextPage} disabled={!record.has_more}>{t("common.next")}</button>
        </div>
      </div>
      <div className="global-agent-record-results">
        {record.results.map((result) => (
          <article key={`${result.window_id}:${result.message.id}`} className="global-agent-record-result">
            <AgentChatMessageCard message={result.message} highlightMatches={result.matches} />
            <footer>
              <span>{t("globalSearch.agentRecordMeta", { window: result.window_id, provider: result.provider ?? "-" })}</span>
              <button type="button" onClick={() => onSelectWindow(result.window_id)}>
                {t("globalSearch.openTerminal")}
              </button>
            </footer>
          </article>
        ))}
      </div>
    </>
  );
}

function GlobalKanbanResults({
  record,
  isLoading,
  isError,
  isFetching,
  onFocusProjectTodo,
  onNextPage,
  onPreviousPage
}: {
  record: ProjectTodoSearchResponse | null;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
  onNextPage: () => void;
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
        <ResultMeta count={record.results.length} isFetching={isFetching} limit={record.limit} offset={record.offset} total={record.total} />
        <div>
          <button type="button" onClick={onPreviousPage} disabled={record.offset === 0}>{t("common.previous")}</button>
          <button type="button" onClick={onNextPage} disabled={!record.has_more}>{t("common.next")}</button>
        </div>
      </div>
      <div className="global-kanban-results">
        {record.results.map((result) => (
          <KanbanSearchResultCard key={result.id} result={result} onFocusProjectTodo={onFocusProjectTodo} />
        ))}
      </div>
    </>
  );
}

function KanbanSearchResultCard({
  result,
  onFocusProjectTodo
}: {
  result: ProjectTodoSearchResult;
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
}) {
  const { t } = useI18n();
  return (
    <article className="global-kanban-result">
      <header>
        <div>
          <span>{highlightedFieldText(result.project_path, result.matches, "project_path")}</span>
          <strong>{highlightedFieldText(result.title, result.matches, "title")}</strong>
        </div>
        <span className="global-search-status">{highlightedFieldText(result.status, result.matches, "status")}</span>
      </header>
      {result.description && (
        <p>{highlightedFieldText(result.description, result.matches, "description")}</p>
      )}
      <footer>
        <span>
          {result.assigned_agent
            ? t("globalSearch.kanbanMetaWithAgent", { agent: result.assigned_agent, updated: formatDateTime(result.updated_at) })
            : t("globalSearch.kanbanMeta", { updated: formatDateTime(result.updated_at) })}
        </span>
        <button type="button" onClick={() => onFocusProjectTodo(result.project_path, result.id)}>
          {t("globalSearch.openKanban")}
        </button>
      </footer>
    </article>
  );
}
