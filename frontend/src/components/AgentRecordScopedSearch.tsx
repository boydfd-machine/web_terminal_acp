import { useI18n } from "../i18n";
import type { AgentRecordSearchResponse } from "../types";
import { AgentChatMessageCard } from "./AgentRecordContent";
import { UiIcon } from "./UiIcon";

export function AgentRecordScopedSearch({
  draft,
  query,
  record,
  isLoading,
  isError,
  isFetching,
  onDraftChange,
  onSubmit,
  onClear,
  onPreviousPage,
  onNextPage
}: {
  draft: string;
  query: string;
  record: AgentRecordSearchResponse | null;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  onDraftChange?: (draft: string) => void;
  onSubmit?: (query: string) => void;
  onClear?: () => void;
  onPreviousPage?: () => void;
  onNextPage?: () => void;
}) {
  const { t } = useI18n();
  const trimmedQuery = query.trim();
  const active = trimmedQuery.length > 0;
  if (!onDraftChange || !onSubmit || !onClear) {
    return null;
  }
  const count = record?.results.length ?? 0;
  const total = record?.total ?? 0;
  const start = total === 0 || record === null ? 0 : record.offset + 1;
  const end = record === null ? 0 : record.offset + count;

  return (
    <section className="agent-record-search" data-onboarding-id="agent-record-search">
      <form
        className="agent-record-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(draft);
        }}
      >
        <label htmlFor="agent-record-scoped-search">{t("agentRecord.search.label")}</label>
        <div className="agent-record-search-row">
          <input
            id="agent-record-scoped-search"
            type="search"
            value={draft}
            placeholder={t("agentRecord.search.placeholder")}
            onChange={(event) => onDraftChange(event.target.value)}
          />
          <button type="submit" className="ui-icon-button" aria-label={t("agentRecord.search.submit")} title={t("agentRecord.search.submit")}>
            <UiIcon name="search" />
          </button>
          {active && (
            <button type="button" className="ui-icon-button" aria-label={t("agentRecord.search.clear")} title={t("agentRecord.search.clear")} onClick={onClear}>
              <UiIcon name="x" />
            </button>
          )}
        </div>
      </form>
      {active && (
        <div className="agent-record-search-results">
          {isLoading && <p className="muted">{t("agentRecord.search.searching")}</p>}
          {isError && <p className="error" role="alert">{t("agentRecord.search.failed")}</p>}
          {!isLoading && !isError && record !== null && (
            <>
              <div className="agent-record-search-meta">
                <span>
                  {total === 0
                    ? t("agentRecord.search.noResults")
                    : t("agentRecord.search.resultRange", { start, end, total })}
                  {isFetching ? ` · ${t("agentRecord.refreshing")}` : ""}
                </span>
                <div className="agent-record-search-pagination">
                  <button type="button" onClick={onPreviousPage} disabled={record.offset === 0}>{t("common.previous")}</button>
                  <button type="button" onClick={onNextPage} disabled={!record.has_more}>{t("common.next")}</button>
                </div>
              </div>
              <div className="agent-record-search-card-list">
                {record.results.map((result) => (
                  <AgentChatMessageCard
                    key={`${result.window_id}:${result.message.id}`}
                    message={result.message}
                    highlightMatches={result.matches}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
