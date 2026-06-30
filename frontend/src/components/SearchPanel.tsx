import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { search } from "../api";
import { useI18n, type TranslateFn, type TranslationKey } from "../i18n";

const sourceLabelKeys: Partial<Record<string, TranslationKey>> = {
  virtual_window_id: "search.source.window",
  title: "search.source.title",
  tags: "search.source.tags",
  folder_path: "search.source.folder",
  provider: "search.source.provider",
  kind: "search.source.kind"
};

function formatSourceValue(value: string | string[] | null | undefined) {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(", ") : "—";
  }
  return value ?? "—";
}

type SearchPanelProps = {
  clientId: string | null;
  onSelectWindowId?: (windowId: string) => void;
};

export function SearchPanel({ clientId, onSelectWindowId }: SearchPanelProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const searchQuery = useQuery({
    queryKey: ["search", clientId, submitted],
    queryFn: () => search(clientId as string, submitted),
    enabled: clientId !== null && submitted.length > 0
  });
  const completedSearch = submitted.length > 0 && searchQuery.isSuccess;
  const resultCount = searchQuery.data?.results.length ?? 0;

  if (clientId === null) {
    return (
      <section className="search-panel" aria-labelledby="agent-record-search-heading" data-onboarding-id="agent-record-search">
        <h2 id="agent-record-search-heading">{t("search.title")}</h2>
        <p className="muted">{t("search.selectClient")}</p>
      </section>
    );
  }

  return (
    <section className="search-panel" aria-labelledby="agent-record-search-heading" data-onboarding-id="agent-record-search">
      <h2 id="agent-record-search-heading">{t("search.title")}</h2>
      <form
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault();
          const trimmed = query.trim();
          if (!trimmed) {
            setSubmitted("");
            return;
          }
          if (trimmed === submitted) {
            void searchQuery.refetch();
            return;
          }
          setSubmitted(trimmed);
        }}
      >
        <label htmlFor="agent-record-search-input">{t("search.label")}</label>
        <div className="search-form-row">
          <input
            id="agent-record-search-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("search.placeholder")}
          />
          <button type="submit">{t("search.submit")}</button>
        </div>
      </form>
      {searchQuery.isLoading && <p className="muted">{t("search.searching")}</p>}
      {searchQuery.isError && (
        <p className="error" role="alert">
          {t("search.failed")}
        </p>
      )}
      {completedSearch && (
        <p className="muted">
          {resultCount === 0 ? t("search.noResults") : t("search.resultCount", { count: resultCount })}
        </p>
      )}
      <div className="search-results">
        {searchQuery.data?.results.map((result) => {
          const sourceEntries = Object.entries(result.source);
          const windowId = result.source.virtual_window_id;
          return (
            <article key={`${result.index}:${result.id}`} className="search-result">
              <div className="search-result-header">
                <strong>{result.index}</strong>
                {result.score !== null && <span className="muted">{t("search.score", { score: result.score.toFixed(2) })}</span>}
                {windowId && onSelectWindowId && (
                  <button type="button" onClick={() => onSelectWindowId(windowId)}>
                    {t("search.openWindow")}
                  </button>
                )}
              </div>
              <p>{result.snippet || t("search.noSnippet")}</p>
              {sourceEntries.length > 0 && (
                <dl>
                  {sourceEntries.map(([key, value]) => (
                    <div key={key}>
                      <dt>{sourceLabel(key, t)}</dt>
                      <dd>{formatSourceValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function sourceLabel(key: string, t: TranslateFn): string {
  const labelKey = sourceLabelKeys[key];
  return labelKey === undefined ? key : t(labelKey);
}
