import type { WorkStatus } from "../types";
import type { ProjectTodoDispatchTone } from "./projectTodoDispatchStage";

type ProjectTodoAgentStatusIconProps = {
  status: WorkStatus | null;
  terminalLinked: boolean;
  dispatchActive?: boolean;
  dispatchTitle?: string | null;
  dispatchTone?: ProjectTodoDispatchTone | null;
  label?: string;
};

function formatDateTime(value: string | null | undefined): string | null {
  if (value == null) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function statusTitle(status: WorkStatus | null, terminalLinked: boolean, label: string): string {
  if (!terminalLinked) {
    return `${label}: no terminal linked`;
  }
  if (status === null) {
    return `${label}: status unavailable`;
  }
  const lastActivity = formatDateTime(status.last_activity_at);
  return lastActivity === null
    ? `${label}: ${status.label}`
    : `${label}: ${status.label} - Last activity ${lastActivity}`;
}

export function ProjectTodoAgentStatusIcon({
  status,
  terminalLinked,
  dispatchActive = false,
  dispatchTitle = null,
  dispatchTone = null,
  label = "Agent status"
}: ProjectTodoAgentStatusIconProps) {
  const title = dispatchTitle === null ? statusTitle(status, terminalLinked, label) : `${label}: ${dispatchTitle}`;
  const color = dispatchTone ?? status?.color ?? "gray";

  return (
    <span
      className={`project-todo-agent-status-icon ${color}${dispatchActive ? " dispatch-active" : ""}`}
      title={title}
      role="img"
      aria-label={title}
    >
      {dispatchActive ? (
        <span className="project-todo-agent-status-spinner" aria-hidden="true" />
      ) : (
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 8V5" />
          <path d="M8 5h8" />
          <rect x="5" y="8" width="14" height="11" rx="3" />
          <path d="M9 13h.01" />
          <path d="M15 13h.01" />
          <path d="M9.5 16h5" />
        </svg>
      )}
    </span>
  );
}
