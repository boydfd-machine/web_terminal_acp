import type { TranslationKey } from "../i18n";
import { useI18n } from "../i18n";
import { projectPathForWindow } from "../terminalTree";
import type {
  AgentTokenUsage,
  AgentTokenUsageCounts,
  GitWorktreeActivity,
  VirtualWindow,
  WorkStatusState
} from "../types";
import { DetailPathValue, DetailSection, DetailTextValue } from "./DetailValues";
import { GitMergeStatusBadge, gitMergeStatusDetail } from "./GitMergeStatus";
import { WorkStatusBadge } from "./WorkStatusBadge";
import { WindowProjectTodoLinks } from "./WindowProjectTodoLinks";
import { formatDateTime, type SummaryStatus } from "./windowDetailData";

type WindowOverviewPanelProps = {
  allowTitleFolderOverride: boolean;
  clientId: string;
  gitWorktree: GitWorktreeActivity | null;
  item: VirtualWindow;
  manualLocks: string[];
  manualWorkStatusError: boolean;
  manualWorkStatusPending: boolean;
  retryError: boolean;
  retryPending: boolean;
  showGitTab: boolean;
  status: SummaryStatus;
  tags: string[];
  windowId: string;
  onAllowTitleFolderOverrideChange: (allow: boolean) => void;
  onFocusProjectTodo?: (projectPath: string, todoId: string) => void;
  onManualWorkStatusChange: (state: WorkStatusState | null) => void;
  onRetrySummary: () => void;
};

const MANUAL_WORK_STATUS_OPTIONS: Array<{ value: WorkStatusState; labelKey: TranslationKey }> = [
  { value: "WORKING", labelKey: "workStatus.working" },
  { value: "FINISHED", labelKey: "workStatus.finished" },
  { value: "ABORTED", labelKey: "workStatus.aborted" },
  { value: "FAILED", labelKey: "workStatus.failed" },
  { value: "RECENT_ACTIVE", labelKey: "workStatus.recentActive" },
  { value: "LONG_IDLE", labelKey: "workStatus.longIdle" }
];

function formatTokenCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return new Intl.NumberFormat().format(value);
}

function cachedTokenTotal(counts: AgentTokenUsageCounts): number {
  return counts.cached_input_tokens + counts.cache_creation_input_tokens;
}

function tokenProgressMetrics(
  value: number | null | undefined,
  total: number | null | undefined,
  compactLimit?: number | null | undefined
): { compactPercent: number | null; now: number; percent: number; total: number; value: number; warning: boolean } | null {
  if (
    typeof value !== "number"
    || !Number.isFinite(value)
    || typeof total !== "number"
    || !Number.isFinite(total)
    || total <= 0
  ) {
    return null;
  }

  const safeValue = Math.max(0, value);
  const safeCompactLimit = (
    typeof compactLimit === "number"
    && Number.isFinite(compactLimit)
    && compactLimit > 0
    && compactLimit <= total
  ) ? compactLimit : null;
  return {
    compactPercent: safeCompactLimit === null || safeCompactLimit === total
      ? null
      : Math.min(100, (safeCompactLimit / total) * 100),
    now: Math.min(safeValue, total),
    percent: Math.min(100, (safeValue / total) * 100),
    total,
    value: safeValue,
    warning: safeCompactLimit !== null && safeValue >= safeCompactLimit
  };
}

function TokenUsageProgress({
  label,
  compactLimit,
  total,
  value
}: {
  label: string;
  compactLimit?: number | null | undefined;
  total: number | null | undefined;
  value: number | null | undefined;
}) {
  const metrics = tokenProgressMetrics(value, total, compactLimit);
  if (!metrics) {
    return null;
  }

  const className = `token-usage-progress${metrics.warning ? " warning" : ""}`;
  return (
    <span
      aria-label={label}
      aria-valuemax={metrics.total}
      aria-valuemin={0}
      aria-valuenow={metrics.now}
      aria-valuetext={`${formatTokenCount(metrics.value)} / ${formatTokenCount(metrics.total)}`}
      className={className}
      role="progressbar"
      title={`${formatTokenCount(metrics.value)} / ${formatTokenCount(metrics.total)}`}
    >
      {metrics.compactPercent !== null && (
        <span
          className="token-usage-progress-warning-zone"
          style={{ left: `${metrics.compactPercent}%`, width: `${100 - metrics.compactPercent}%` }}
        />
      )}
      <span
        className="token-usage-progress-fill"
        style={{ minWidth: metrics.percent > 0 ? 2 : 0, width: `${metrics.percent}%` }}
      />
    </span>
  );
}

function tokenProgressTotal(usage: AgentTokenUsage): number | null {
  return usage.context_window ?? usage.auto_compact_token_limit ?? null;
}

function tokenProgressValue(usage: AgentTokenUsage): number | null {
  return usage.context?.total_tokens ?? usage.total.total_tokens ?? null;
}

function providerLabel(usage: AgentTokenUsage): string {
  return usage.providers.length > 0 ? usage.providers.join(", ") : "-";
}

function tokenLimitLabel(usage: AgentTokenUsage, t: (key: TranslationKey, params?: Record<string, string>) => string): string | null {
  if (usage.context_window !== null) {
    const total = formatTokenCount(usage.context_window);
    const compact = usage.auto_compact_token_limit == null
      ? null
      : formatTokenCount(usage.auto_compact_token_limit);
    return t("window.overview.contextWindowTokens", {
      total: compact === null ? total : `${total} (${compact})`
    });
  }
  if (usage.auto_compact_token_limit != null) {
    return t("window.overview.compactLimitTokens", {
      total: formatTokenCount(usage.auto_compact_token_limit)
    });
  }
  return null;
}

export function WindowOverviewPanel({
  allowTitleFolderOverride,
  clientId,
  gitWorktree,
  item,
  manualLocks,
  manualWorkStatusError,
  manualWorkStatusPending,
  retryError,
  retryPending,
  showGitTab,
  status,
  tags,
  windowId,
  onAllowTitleFolderOverrideChange,
  onFocusProjectTodo,
  onManualWorkStatusChange,
  onRetrySummary
}: WindowOverviewPanelProps) {
  const { t } = useI18n();
  const itemProjectPath = projectPathForWindow(item);
  const manualWorkStatusValue = item.work_status.source === "manual" ? item.work_status.state : "auto";
  const tokenUsage = item.agent_token_usage;
  const tokenUsageLimitLabel = tokenUsage ? tokenLimitLabel(tokenUsage, t) : null;

  return (
    <div className="detail-overview">
      <DetailSection title={t("window.overview.basics")}>
        <dt>{t("window.overview.status")}</dt>
        <dd><DetailTextValue value={item.status} /></dd>
        <dt>{t("window.overview.created")}</dt>
        <dd><DetailTextValue value={formatDateTime(item.created_at)} /></dd>
        <dt>{t("window.overview.lastActive")}</dt>
        <dd><DetailTextValue value={formatDateTime(item.last_active_at)} /></dd>
        <dt>{t("window.overview.cwd")}</dt>
        <dd><DetailPathValue value={item.cwd} /></dd>
        {onFocusProjectTodo && (
          <>
            <dt>{t("window.overview.projectTodos")}</dt>
            <dd>
              <WindowProjectTodoLinks
                clientId={clientId}
                projectPath={itemProjectPath}
                windowId={item.id}
                onFocusProjectTodo={onFocusProjectTodo}
              />
            </dd>
          </>
        )}
        {gitWorktree && (
          <>
            <dt>{t("window.overview.gitWorktree")}</dt>
            <dd><DetailPathValue value={gitWorktree.worktree_root} /></dd>
            <dt>{t("window.overview.branch")}</dt>
            <dd><DetailTextValue value={gitWorktree.branch ?? "-"} /></dd>
            <dt>{t("window.overview.merge")}</dt>
            <dd>
              <span className="detail-git-merge-status">
                <GitMergeStatusBadge source={gitWorktree} />
                <DetailTextValue
                  value={gitMergeStatusDetail(gitWorktree, t)}
                  tone={gitWorktree.merge_attention_required ? "error" : "muted"}
                />
              </span>
            </dd>
          </>
        )}
        <dt>{t("window.overview.tmux")}</dt>
        <dd><DetailTextValue value={`${item.tmux_session ?? "-"}:${item.tmux_window_id ?? "-"}`} /></dd>
        <dt>{t("window.overview.tmuxWindowIndex")}</dt>
        <dd><DetailTextValue value={item.tmux_window_index ?? "-"} /></dd>
        <dt>{t("window.overview.manualLocks")}</dt>
        <dd><DetailTextValue value={manualLocks.length > 0 ? manualLocks.join(", ") : "-"} /></dd>
      </DetailSection>

      <DetailSection title={t("window.overview.agentState")}>
        <dt>{t("window.overview.lastShellCommand")}</dt>
        <dd>
          <DetailTextValue
            value={item.last_terminal_command_at ? formatDateTime(item.last_terminal_command_at) : "-"}
          />
        </dd>
        <dt>{t("window.overview.lastAgentEvent")}</dt>
        <dd><DetailTextValue value={item.last_agent_event_at ? formatDateTime(item.last_agent_event_at) : "-"} /></dd>
        <dt>{t("window.overview.workStatus")}</dt>
        <dd>
          <span className="detail-work-status">
            <WorkStatusBadge status={item.work_status} />
            <span className="muted">
              {item.work_status.source === "manual" && item.work_status.manual_updated_at
                ? t("window.overview.manualAt", { time: formatDateTime(item.work_status.manual_updated_at) })
                : item.work_status.last_activity_at
                  ? t("window.overview.lastActivityAt", { time: formatDateTime(item.work_status.last_activity_at) })
                  : t("window.overview.noActivity")}
            </span>
            <span className="manual-work-status-controls">
              <select
                aria-label={t("window.overview.manualWorkStatus")}
                disabled={manualWorkStatusPending}
                value={manualWorkStatusValue}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  onManualWorkStatusChange(nextValue === "auto" ? null : (nextValue as WorkStatusState));
                }}
              >
                <option value="auto">{t("window.overview.auto")}</option>
                {MANUAL_WORK_STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
                ))}
              </select>
              {item.work_status.source === "manual" && (
                <button
                  type="button"
                  disabled={manualWorkStatusPending}
                  onClick={() => onManualWorkStatusChange(null)}
                >
                  {t("window.overview.clear")}
                </button>
              )}
            </span>
          </span>
          {manualWorkStatusError && (
            <p className="error detail-inline-error" role="alert">{t("window.overview.updateWorkStatusFailed")}</p>
          )}
        </dd>
        {tokenUsage && (
          <>
            <dt>{t("window.overview.contextTokens")}</dt>
            <dd>
              <span className="token-usage-line">
                <strong>{formatTokenCount(tokenUsage.context?.total_tokens)}</strong>
                {tokenUsageLimitLabel !== null && <span className="muted">{tokenUsageLimitLabel}</span>}
                <TokenUsageProgress
                  compactLimit={tokenUsage.auto_compact_token_limit}
                  label={t("window.overview.contextTokens")}
                  total={tokenProgressTotal(tokenUsage)}
                  value={tokenProgressValue(tokenUsage)}
                />
              </span>
            </dd>
            <dt>{t("window.overview.totalTokens")}</dt>
            <dd>
              <span className="token-usage-line">
                <strong>{formatTokenCount(tokenUsage.total.total_tokens)}</strong>
                <span className="muted">
                  {t("window.overview.cachedTokens", {
                    count: formatTokenCount(cachedTokenTotal(tokenUsage.total))
                  })}
                </span>
              </span>
            </dd>
            <dt>{t("window.overview.tokenDetails")}</dt>
            <dd>
              <span className="token-usage-breakdown">
                <span>
                  {t("window.overview.inputTokens", { count: formatTokenCount(tokenUsage.total.input_tokens) })}
                </span>
                <span>
                  {t("window.overview.outputTokens", { count: formatTokenCount(tokenUsage.total.output_tokens) })}
                </span>
                {tokenUsage.total.reasoning_output_tokens > 0 && (
                  <span>
                    {t("window.overview.reasoningTokens", {
                      count: formatTokenCount(tokenUsage.total.reasoning_output_tokens)
                    })}
                  </span>
                )}
              </span>
            </dd>
            <dt>{t("window.overview.tokenSource")}</dt>
            <dd>
              <DetailTextValue
                value={t("window.overview.tokenSourceValue", {
                  count: String(tokenUsage.event_count),
                  providers: providerLabel(tokenUsage)
                })}
              />
            </dd>
          </>
        )}
        <dt>{t("window.overview.summary")}</dt>
        <dd><DetailTextValue value={item.summary ?? t("window.overview.noSummary")} /></dd>
        <dt>{t("window.overview.tags")}</dt>
        <dd>
          {tags.length > 0 ? (
            <span className="detail-tags">
              {tags.map((tag) => (
                <span key={tag} title={tag}>{tag}</span>
              ))}
            </span>
          ) : (
            "-"
          )}
        </dd>
        <dt>{t("window.overview.summaryJob")}</dt>
        <dd><DetailTextValue value={status.label} tone={status.tone} /></dd>
        {item.summary_job?.last_error && (
          <>
            <dt>{t("window.overview.lastError")}</dt>
            <dd><DetailTextValue value={item.summary_job.last_error} tone="error" /></dd>
          </>
        )}
        {item.summary_job && (
          <>
            <dt>{t("window.overview.attempts")}</dt>
            <dd><DetailTextValue value={String(item.summary_job.attempts)} /></dd>
          </>
        )}
        {item.summary_job?.trigger_reason && (
          <>
            <dt>{t("window.overview.trigger")}</dt>
            <dd><DetailTextValue value={item.summary_job.trigger_reason} /></dd>
          </>
        )}
        {item.summary_job?.run_after && (
          <>
            <dt>{t("window.overview.runAfter")}</dt>
            <dd><DetailTextValue value={formatDateTime(item.summary_job.run_after)} /></dd>
          </>
        )}
      </DetailSection>
      <div className="retry-summary">
        <label>
          <input
            type="checkbox"
            checked={allowTitleFolderOverride}
            disabled={retryPending}
            onChange={(event) => onAllowTitleFolderOverrideChange(event.target.checked)}
          />
          {t("window.overview.allowTitleFolderOverride")}
        </label>
        <button disabled={retryPending} onClick={onRetrySummary}>
          {t("window.overview.retrySummary")}
        </button>
      </div>
      {retryError && <p className="error" role="alert">{t("window.overview.retrySummaryFailed")}</p>}
      {!showGitTab && (
        <p className="muted detail-git-hint">
          {t("window.overview.gitTrackingHint", { skill: "web-terminal-git-worktree" })}
        </p>
      )}
    </div>
  );
}
