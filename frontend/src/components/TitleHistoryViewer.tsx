import type { WindowTitleHistory, WindowTitleHistoryItem } from "../types";
import { useI18n, type TranslateFn } from "../i18n";

type Props = {
  history: WindowTitleHistory | null;
  isLoading?: boolean;
  isError?: boolean;
  isFetching?: boolean;
  onPreviousPage?: () => void;
  onNextPage?: () => void;
};

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function sourceLabel(source: string, t: TranslateFn): string {
  switch (source) {
    case "initial":
      return t("history.title.source.initial");
    case "baseline":
      return t("history.title.source.baseline");
    case "summary":
      return t("history.title.source.summary");
    case "manual":
      return t("history.title.source.manual");
    default:
      return source;
  }
}

function pageLabel(history: WindowTitleHistory, t: TranslateFn): string {
  if (history.total === 0) {
    return t("history.title.zero");
  }
  const start = history.offset + 1;
  const end = history.offset + history.items.length;
  return t("history.title.range", { start, end, total: history.total });
}

function TitleHistoryRow({ item }: { item: WindowTitleHistoryItem }) {
  const { t } = useI18n();

  return (
    <article className="title-history-item">
      <header>
        <div>
          <strong title={item.title}>{item.title}</strong>
          <span>{sourceLabel(item.source, t)}</span>
        </div>
        <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
      </header>
      <p>{item.summary ?? t("history.title.noSummary")}</p>
    </article>
  );
}

export function TitleHistoryViewer({
  history,
  isLoading = false,
  isError = false,
  isFetching = false,
  onPreviousPage,
  onNextPage
}: Props) {
  const { t } = useI18n();

  if (isLoading) {
    return <p className="muted">{t("history.title.loading")}</p>;
  }
  if (isError) {
    return <p className="error" role="alert">{t("history.title.failed")}</p>;
  }
  if (history === null || history.items.length === 0) {
    return <p className="muted">{t("history.title.empty")}</p>;
  }

  return (
    <div className="title-history-viewer">
      <div className="agent-record-pagination">
        <span>{pageLabel(history, t)}{isFetching ? ` · ${t("history.refreshing")}` : ""}</span>
        <div>
          <button
            type="button"
            disabled={history.offset === 0 || isFetching}
            onClick={onPreviousPage}
          >
            {t("history.previous")}
          </button>
          <button
            type="button"
            disabled={!history.has_more || isFetching}
            onClick={onNextPage}
          >
            {t("history.next")}
          </button>
        </div>
      </div>
      <div className="title-history-list">
        {history.items.map((item) => (
          <TitleHistoryRow key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
