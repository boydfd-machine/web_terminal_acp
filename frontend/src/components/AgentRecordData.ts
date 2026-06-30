import type {
  AgentChatMessage,
  AgentChatRecord,
  AgentChatRoleFilter,
  AgentEventProjection,
  AgentRecord,
  AgentRecordDisplayMode,
  AgentRecordEvent,
  AgentRecordSearchResponse,
  AgentSession
} from "../types";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import type { TranslateFn, TranslationKey } from "../i18n";

export type EventTone =
  | "base-instructions"
  | "system"
  | "developer"
  | "context"
  | "user"
  | "user-input"
  | "agent"
  | "reasoning"
  | "tool-call"
  | "tool-result"
  | "subagent-call"
  | "subagent-result"
  | "subagent-context"
  | "lifecycle"
  | "event";
export type BodyFormat = "markdown" | "json";
export type EventView = {
  tone: EventTone;
  label: string;
  body: string;
  subtype: string | null;
  bodyFormat?: BodyFormat;
  targetSessionId?: string | null;
};
export type AgentNode = { id: string; label: string; meta: string; children: AgentNode[] };
export type AgentRecordJumpRequest = { sessionId: string; originMessageId?: string };
export type AgentRecordPageOffset = { chatOffset?: number; detailOffset?: number };
export type AgentRecordTimeRange = { start: string; end: string };
export type AgentRecordViewProps = {
  mode: AgentRecordDisplayMode;
  chatRoleFilter: AgentChatRoleFilter;
  chatRecord: AgentChatRecord | null;
  detailRecord: AgentRecord | null;
  sessions: AgentSession[];
  isLoading?: boolean;
  isError?: boolean;
  isFetching?: boolean;
  projectFileContext?: ProjectFileLinkContext | null;
  onModeChange: (mode: AgentRecordDisplayMode) => void;
  onChatRoleFilterChange: (role: AgentChatRoleFilter) => void;
  jumpRequest?: AgentRecordJumpRequest | null;
  onOpenSubagent?: (sessionId: string, originMessageId?: string) => void;
  onSessionChange?: (sessionId: string | null, pageOffset?: AgentRecordPageOffset) => void;
  onPreviousPage?: () => void;
  onNextPage?: () => void;
  searchDraft?: string;
  searchQuery?: string;
  searchRecord?: AgentRecordSearchResponse | null;
  searchIsLoading?: boolean;
  searchIsError?: boolean;
  searchIsFetching?: boolean;
  onSearchDraftChange?: (draft: string) => void;
  onSearchSubmit?: (query: string) => void;
  onSearchClear?: () => void;
  onPreviousSearchPage?: () => void;
  onNextSearchPage?: () => void;
};
export type AgentRecordViewerProps = AgentRecordViewProps & {
  onExpand: () => void;
  expandShortcutLabel?: string;
  quickInputDraft?: string;
  canSendQuickInput?: boolean;
  onQuickInputDraftChange?: (draft: string) => void;
  onQuickInputSubmit?: (draft: string) => boolean;
};
export type AgentRecordModalProps = AgentRecordViewProps & {
  open: boolean;
  terminalStatusLabel?: string;
  terminalStatusTone?: "connected" | "connecting" | "reconnecting" | "unavailable" | "error";
  quickInputDraft?: string;
  canSendQuickInput?: boolean;
  onQuickInputDraftChange?: (draft: string) => void;
  onQuickInputSubmit?: (draft: string) => boolean;
  onClose: () => void;
};
export type PageInfo = {
  total: number;
  limit: number;
  offset: number;
  count: number;
  hasMore: boolean;
  totalExact?: boolean;
  noun: string;
  nounKey: TranslationKey;
};
export const EVENT_LABELS: Record<EventTone, string> = {
  "base-instructions": "Base instructions",
  system: "System message",
  developer: "Developer instructions",
  context: "Context",
  user: "User message",
  "user-input": "User input",
  agent: "Agent response",
  reasoning: "Agent reasoning",
  "tool-call": "Tool call",
  "tool-result": "Tool response",
  "subagent-call": "Subagent call",
  "subagent-result": "Subagent result",
  "subagent-context": "Subagent context",
  lifecycle: "Lifecycle",
  event: "Event"
};
const EVENT_LABEL_KEYS: Record<EventTone, TranslationKey> = {
  "base-instructions": "agentRecord.event.baseInstructions",
  system: "agentRecord.event.system",
  developer: "agentRecord.event.developer",
  context: "agentRecord.event.context",
  user: "agentRecord.event.user",
  "user-input": "agentRecord.event.userInput",
  agent: "agentRecord.event.agent",
  reasoning: "agentRecord.event.reasoning",
  "tool-call": "agentRecord.event.toolCall",
  "tool-result": "agentRecord.event.toolResult",
  "subagent-call": "agentRecord.event.subagentCall",
  "subagent-result": "agentRecord.event.subagentResult",
  "subagent-context": "agentRecord.event.subagentContext",
  lifecycle: "agentRecord.event.lifecycle",
  event: "agentRecord.event.event"
};

export const CHAT_ROLE_FILTER_LABELS: Record<AgentChatRoleFilter, string> = {
  all: "All",
  user: "User",
  agent: "Agent",
  subagent_call: "Subagent call",
  subagent_result: "Subagent result"
};
const CHAT_ROLE_FILTER_LABEL_KEYS: Record<AgentChatRoleFilter, TranslationKey> = {
  all: "agentRecord.role.all",
  user: "agentRecord.role.user",
  agent: "agentRecord.role.agent",
  subagent_call: "agentRecord.role.subagentCall",
  subagent_result: "agentRecord.role.subagentResult"
};

export function json(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function jsonMarkdown(value: unknown): string {
  return `\`\`\`json\n${json(value)}\n\`\`\``;
}

export function eventToneClass(tone: string): EventTone {
  return EVENT_LABELS[tone as EventTone] ? tone as EventTone : "event";
}

export function projectionView(projection: AgentEventProjection): EventView {
  return {
    tone: eventToneClass(projection.tone),
    label: projection.label,
    body: projection.body,
    subtype: projection.subtype,
    bodyFormat: projection.body_format,
    targetSessionId: projection.target_session_id
  };
}

export function eventLabel(tone: EventTone, t?: TranslateFn): string {
  return t?.(EVENT_LABEL_KEYS[tone]) ?? EVENT_LABELS[tone];
}

export function chatRoleFilterLabel(role: AgentChatRoleFilter, t?: TranslateFn): string {
  return t?.(CHAT_ROLE_FILTER_LABEL_KEYS[role]) ?? CHAT_ROLE_FILTER_LABELS[role];
}

export function eventView(event: AgentRecordEvent, t?: TranslateFn): EventView {
  if (event.projection) return projectionView(event.projection);
  return {
    tone: "event",
    label: eventLabel("event", t),
    body: jsonMarkdown(event.payload_json),
    bodyFormat: "json",
    subtype: event.kind
  };
}
export function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function timeRangeFromDates(values: string[]): AgentRecordTimeRange | null {
  let start: { timestamp: number; value: string } | null = null;
  let end: { timestamp: number; value: string } | null = null;

  for (const value of values) {
    const timestamp = Date.parse(value);
    if (Number.isNaN(timestamp)) {
      continue;
    }
    if (start === null || timestamp < start.timestamp) {
      start = { timestamp, value };
    }
    if (end === null || timestamp > end.timestamp) {
      end = { timestamp, value };
    }
  }

  if (start !== null && end !== null) {
    return { start: start.value, end: end.value };
  }
  if (values.length === 0) {
    return null;
  }
  return { start: values[0], end: values[values.length - 1] };
}

export function formatTimeRange(range: AgentRecordTimeRange, t?: TranslateFn): string {
  const start = formatDateTime(range.start);
  const end = formatDateTime(range.end);
  return t?.("agentRecord.metaTimeRange", { start, end }) ?? `Start ${start} · End ${end}`;
}

function appendTimeRangeMeta(meta: string, range: AgentRecordTimeRange | null, t?: TranslateFn): string {
  return range ? `${meta} · ${formatTimeRange(range, t)}` : meta;
}

export function tail(value: string | null): string | null {
  if (value === null) return null;
  const parts = value.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : value;
}

export function sessionLabel(session: AgentSession): string {
  return session.title ?? tail(session.source_path) ?? session.source_id;
}

export function sessionCreatedTimestamp(session: AgentSession): number {
  const created = Date.parse(session.created_at);
  return Number.isNaN(created) ? 0 : created;
}

export function sortSessionsByCreation(sessions: AgentSession[]): AgentSession[] {
  return [...sessions].sort((left, right) => {
    const delta = sessionCreatedTimestamp(left) - sessionCreatedTimestamp(right);
    if (delta !== 0) {
      return delta;
    }
    return left.id.localeCompare(right.id);
  });
}

export function pickInitialSessionId(sessions: AgentSession[]): string | null {
  return sortSessionsByCreation(sessions)[0]?.id ?? null;
}

export function hasSubagentSessionNavigation(
  sessions: AgentSession[],
  chatRecord: AgentChatRecord | null,
  detailRecord: AgentRecord | null
): boolean {
  if (sessions.length < 2) {
    return false;
  }
  const sessionIds = new Set(sessions.map((session) => session.id));
  const sourceIds = new Set(sessions.map((session) => session.source_id));
  const linksKnownSession = (targetSessionId: string | null, targetSessionSourceId: string | null) => (
    (targetSessionId !== null && sessionIds.has(targetSessionId))
    || (targetSessionSourceId !== null && sourceIds.has(targetSessionSourceId))
  );

  if (sessions.some((session) => parentSourceFromSession(session) !== null)) {
    return true;
  }
  if (chatRecord?.messages.some((message) => (
    linksKnownSession(message.target_session_id, message.target_session_source_id)
  ))) {
    return true;
  }
  return detailRecord?.events.some((event) => {
    const projection = event.projection;
    if (
      projection !== null
      && linksKnownSession(projection.target_session_id, projection.target_session_source_id)
    ) {
      return true;
    }
    return event.payload_json.isSidechain === true
      && event.ai_session_id !== null
      && sessionIds.has(event.ai_session_id);
  }) ?? false;
}

export function defaultAgentMessageType(message: AgentChatMessage): "user" | "agent" | "subagent_call" | "subagent_result" {
  if (message.agent_message_type === "subagent_call" || message.agent_message_type === "subagent_result") {
    return message.agent_message_type;
  }
  return message.role;
}

export function chatSpeakerLabel(message: AgentChatMessage, t?: TranslateFn): string {
  switch (defaultAgentMessageType(message)) {
    case "subagent_call":
      return t?.("agentRecord.speaker.subagentCall") ?? "Main Agent -> Subagent";
    case "subagent_result":
      return t?.("agentRecord.speaker.subagentResult") ?? "Subagent -> Agent";
    case "agent":
      return t?.("agentRecord.speaker.agent") ?? "Agent";
    case "user":
      return t?.("agentRecord.speaker.user") ?? "User";
  }
}

export function chatMessageClass(message: AgentChatMessage): string {
  return `agent-chat-message-${defaultAgentMessageType(message).replace("_", "-")}`;
}

export function parentSourceFromPath(sourcePath: string | null): string | null {
  return sourcePath?.match(/\/([^/]+)\/subagents\/agent-[^/]+\.jsonl$/)?.[1] ?? null;
}

export function parentSourceFromSession(session: AgentSession): string | null {
  if (session.source_path) {
    return parentSourceFromPath(session.source_path);
  }
  return null;
}

export function buildAgentTree(record: AgentRecord, t?: TranslateFn): AgentNode[] {
  const nodes = new Map<string, AgentNode>();
  const sourceToNode = new Map<string, AgentNode>();
  const roots: AgentNode[] = [];
  for (const session of record.sessions) {
    const node = { id: session.id, label: sessionLabel(session), meta: `${session.provider} · ${session.source_id}`, children: [] };
    nodes.set(session.id, node);
    sourceToNode.set(session.source_id, node);
  }
  for (const session of record.sessions) {
    const node = nodes.get(session.id);
    const parent = sourceToNode.get(parentSourceFromSession(session) ?? "");
    if (!node) continue;
    if (parent && parent.id !== node.id) parent.children.push(node);
    else roots.push(node);
  }
  for (const session of record.sessions) {
    const hasSidechain = record.events.some((event) => event.ai_session_id === session.id && event.payload_json.isSidechain === true);
    const node = nodes.get(session.id);
    if (hasSidechain && node) node.children.push({
      id: `${session.id}:sidechain`,
      label: t?.("agentRecord.sidechain") ?? "Sidechain / subagent",
      meta: t?.("agentRecord.sidechainEvents") ?? "Claude sidechain events",
      children: []
    });
  }
  if (roots.length === 0 && record.events.length > 0) roots.push({
    id: "events",
    label: t?.("agentRecord.unlinkedEvents") ?? "Unlinked agent events",
    meta: t?.("agentRecord.eventsCount", { count: record.events.length }) ?? `${record.events.length} events`,
    children: []
  });
  return roots;
}
export function recordMeta(
  mode: AgentRecordDisplayMode,
  chatRoleFilter: AgentChatRoleFilter,
  chatRecord: AgentChatRecord | null,
  detailRecord: AgentRecord | null,
  isLoading: boolean,
  isError: boolean,
  t?: TranslateFn
): string {
  if (isLoading) return t?.("agentRecord.metaLoading") ?? "Loading";
  if (isError) return t?.("agentRecord.metaUnavailable") ?? "Unavailable";
  if (mode === "chat") {
    if (chatRecord === null) return t?.("agentRecord.metaNoData") ?? "No data";
    const scope = chatRoleFilter === "all"
      ? t?.("agentRecord.chatMessages") ?? "chat messages"
      : t?.("agentRecord.roleMessages", { role: chatRoleFilterLabel(chatRoleFilter, t).toLocaleLowerCase() })
        ?? `${CHAT_ROLE_FILTER_LABELS[chatRoleFilter].toLocaleLowerCase()} messages`;
    return appendTimeRangeMeta(
      `${chatRecord.messages_total}${chatRecord.messages_total_exact === false ? "+" : ""} ${scope}`,
      timeRangeFromDates(chatRecord.messages.map((message) => message.created_at)),
      t
    );
  }
  if (detailRecord === null) return t?.("agentRecord.metaNoData") ?? "No data";
  return appendTimeRangeMeta(
    t?.("agentRecord.agentsEvents", { agents: detailRecord.sessions.length, events: detailRecord.events_total })
      ?? `${detailRecord.sessions.length} agents · ${detailRecord.events_total} events`,
    timeRangeFromDates(detailRecord.events.map((event) => event.created_at)),
    t
  );
}

export function pageInfo(mode: AgentRecordDisplayMode, chatRecord: AgentChatRecord | null, detailRecord: AgentRecord | null): PageInfo | null {
  if (mode === "chat") {
    if (chatRecord === null) return null;
    return {
      total: chatRecord.messages_total,
      limit: chatRecord.messages_limit,
      offset: chatRecord.messages_offset,
      count: chatRecord.messages.length,
      hasMore: chatRecord.messages_has_more,
      totalExact: chatRecord.messages_total_exact,
      noun: "messages",
      nounKey: "agentRecord.messages"
    };
  }
  if (detailRecord === null) return null;
  return {
    total: detailRecord.events_total,
    limit: detailRecord.events_limit,
    offset: detailRecord.events_offset,
    count: detailRecord.events.length,
    hasMore: detailRecord.events_has_more,
    noun: "events",
    nounKey: "agentRecord.events"
  };
}

export function pageRange(info: PageInfo, t?: TranslateFn): string {
  const noun = t?.(info.nounKey) ?? info.noun;
  if (info.total === 0) return t?.("agentRecord.zeroOfTotal", { noun }) ?? `0 of 0 ${noun}`;
  const start = info.offset + 1;
  const end = info.offset + info.count;
  return t?.("agentRecord.countOfTotal", {
    start,
    end,
    total: `${info.total}${info.totalExact === false ? "+" : ""}`,
    noun
  }) ?? `${start}-${end} of ${info.total}${info.totalExact === false ? "+" : ""} ${noun}`;
}
