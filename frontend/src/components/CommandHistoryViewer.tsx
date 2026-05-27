import type { CommandHistory, CommandHistoryItem } from "../types";

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

function exitStatusLabel(value: number | string | null): string {
  if (value === null) {
    return "running";
  }
  return String(value);
}

function CommandHistoryRow({ item }: { item: CommandHistoryItem }) {
  return (
    <article className="command-history-item">
      <header>
        <code>{item.command}</code>
        <time dateTime={item.captured_at}>{formatDateTime(item.captured_at)}</time>
      </header>
      <dl className="detail-list command-history-meta">
        <dt>CWD</dt>
        <dd>{item.cwd ?? "-"}</dd>
        <dt>Shell</dt>
        <dd>{item.shell ?? "-"}</dd>
        <dt>Exit</dt>
        <dd>{exitStatusLabel(item.exit_status)}</dd>
        <dt>Sequence</dt>
        <dd>{item.sequence ?? "-"}</dd>
        <dt>Finished</dt>
        <dd>{formatDateTime(item.finished_at)}</dd>
      </dl>
    </article>
  );
}

function pageLabel(history: CommandHistory): string {
  if (history.commands_total === 0) {
    return "0 commands";
  }
  const start = history.commands_offset + 1;
  const end = history.commands_offset + history.commands.length;
  return `${start}-${end} of ${history.commands_total}`;
}

export function CommandHistoryViewer({
  history,
  isLoading = false,
  isError = false,
  isFetching = false,
  onPreviousPage,
  onNextPage
}: Props) {
  if (isLoading) {
    return <p className="muted">Loading command history...</p>;
  }
  if (isError) {
    return <p className="error" role="alert">Failed to load command history.</p>;
  }
  if (history === null || history.commands.length === 0) {
    return <p className="muted">No command history captured yet.</p>;
  }

  return (
    <div className="command-history-viewer">
      <div className="agent-record-pagination">
        <span>{pageLabel(history)}{isFetching ? " · refreshing" : ""}</span>
        <div>
          <button
            type="button"
            disabled={history.commands_offset === 0 || isFetching}
            onClick={onPreviousPage}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!history.commands_has_more || isFetching}
            onClick={onNextPage}
          >
            Next
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
