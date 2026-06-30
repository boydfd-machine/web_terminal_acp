import type { CommandHistory, CommandHistoryItem } from "../types";
import { useI18n, type TranslateFn } from "../i18n";

type Props = {
  history: CommandHistory | null;
  isLoading?: boolean;
  isError?: boolean;
  isFetching?: boolean;
  onPreviousPage?: () => void;
  onNextPage?: () => void;
};

function formatDateTime(value: string | null): string {
  if (value === null) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function exitStatusLabel(value: number | string | null, t: TranslateFn): string {
  if (value === null) {
    return t("history.running");
  }
  return String(value);
}

function CommandHistoryRow({ item }: { item: CommandHistoryItem }) {
  const { t } = useI18n();

  return (
    <article className="command-history-item">
      <header>
        <code>{item.command}</code>
        <time dateTime={item.captured_at}>{formatDateTime(item.captured_at)}</time>
      </header>
      <dl className="detail-list command-history-meta">
        <dt>{t("history.command.cwd")}</dt>
        <dd>{item.cwd ?? "-"}</dd>
        <dt>{t("history.command.shell")}</dt>
        <dd>{item.shell ?? "-"}</dd>
        <dt>{t("history.command.exit")}</dt>
        <dd>{exitStatusLabel(item.exit_status, t)}</dd>
        <dt>{t("history.command.sequence")}</dt>
        <dd>{item.sequence ?? "-"}</dd>
        <dt>{t("history.command.finished")}</dt>
        <dd>{formatDateTime(item.finished_at)}</dd>
      </dl>
    </article>
  );
}

function pageLabel(history: CommandHistory, t: TranslateFn): string {
  if (history.commands_total === 0) {
    return t("history.command.zero");
  }
  const start = history.commands_offset + 1;
  const end = history.commands_offset + history.commands.length;
  return t("history.command.range", { start, end, total: history.commands_total });
}

export function CommandHistoryViewer({
  history,
  isLoading = false,
  isError = false,
  isFetching = false,
  onPreviousPage,
  onNextPage
}: Props) {
  const { t } = useI18n();

  if (isLoading) {
    return <p className="muted">{t("history.command.loading")}</p>;
  }
  if (isError) {
    return <p className="error" role="alert">{t("history.command.failed")}</p>;
  }
  if (history === null || history.commands.length === 0) {
    return <p className="muted">{t("history.command.empty")}</p>;
  }

  return (
    <div className="command-history-viewer">
      <div className="agent-record-pagination">
        <span>{pageLabel(history, t)}{isFetching ? ` · ${t("history.refreshing")}` : ""}</span>
        <div>
          <button
            type="button"
            disabled={history.commands_offset === 0 || isFetching}
            onClick={onPreviousPage}
          >
            {t("history.previous")}
          </button>
          <button
            type="button"
            disabled={!history.commands_has_more || isFetching}
            onClick={onNextPage}
          >
            {t("history.next")}
          </button>
        </div>
      </div>
      <div className="command-history-list">
        {history.commands.map((item) => (
          <CommandHistoryRow key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
