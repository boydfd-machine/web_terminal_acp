import type { CSSProperties, DragEvent, MouseEvent } from "react";

import { useI18n, type TranslateFn } from "../i18n";
import type { ProjectTodoListItem } from "../types";
import { formatProjectTodoShortDate } from "./projectTodoDisplay";
import { projectTodoDispatchStageActive, projectTodoDispatchTitle, projectTodoDispatchTone, type ProjectTodoDispatchTone } from "./projectTodoDispatchStage";
import { ProjectTodoAgentStatusIcon } from "./ProjectTodoAgentStatusIcon";
import { GitMergeStatusBadge, gitMergeAttentionRequired } from "./GitMergeStatus";
import {
  projectTodoAssignee,
  projectTodoTerminalTags,
  projectTodoTopicLabel,
  type ProjectTodoTreeNode
} from "../features/projectTodos/projectTodoBoardModel";
import type { ProjectTodoCardSharedProps } from "./ProjectTodoBoardTypes";
import { ProjectTodoAttachmentCount, ProjectTodoAttachmentUploadButton } from "./ProjectTodoAttachments";
import { ProjectTodoScheduleToggle } from "./ProjectTodoScheduleControls";
import { ProjectTodoCardArtifactStatus } from "./ProjectTodoCardArtifacts";
import { ProjectTodoCreateChildButton } from "./ProjectTodoCreateChildButton";
import { ProjectTodoCardAgentConversationButton } from "./ProjectTodoCardAgentConversation";
import { UiIcon } from "./UiIcon";

export function ProjectTodoTree({
  cardProps,
  collapsedKeys,
  nodes,
  onToggleNode
}: {
  cardProps: ProjectTodoCardSharedProps;
  collapsedKeys: Set<string>;
  nodes: ProjectTodoTreeNode[];
  onToggleNode: (nodeKey: string) => void;
}) {
  return (
    <div className="project-todo-tree-list">
      {nodes.map((node) => (
        <ProjectTodoTreeNodeView
          key={node.key}
          cardProps={cardProps}
          collapsedKeys={collapsedKeys}
          node={node}
          onToggleNode={onToggleNode}
        />
      ))}
    </div>
  );
}

function ProjectTodoTreeNodeView({
  cardProps,
  collapsedKeys,
  node,
  onToggleNode
}: {
  cardProps: ProjectTodoCardSharedProps;
  collapsedKeys: Set<string>;
  node: ProjectTodoTreeNode;
  onToggleNode: (nodeKey: string) => void;
}) {
  const collapsed = collapsedKeys.has(node.key);
  const hasChildren = node.children.length > 0;
  return (
    <div className="project-todo-tree-node">
      <button
        type="button"
        className="project-todo-tree-node-header"
        style={{ "--tree-depth": node.depth } as CSSProperties}
        aria-expanded={!collapsed}
        onClick={() => onToggleNode(node.key)}
      >
        <ChevronIcon collapsed={collapsed || !hasChildren} muted={!hasChildren} />
        <span>{node.label}</span>
        <strong>{node.count}</strong>
      </button>
      {!collapsed && (
        <>
          {node.todos.map((todo) => (
            <ProjectTodoCard key={todo.id} todo={todo} compactTree treeDepth={node.depth + 1} {...cardProps} />
          ))}
          {node.children.map((child) => (
            <ProjectTodoTreeNodeView
              key={child.key}
              cardProps={cardProps}
              collapsedKeys={collapsedKeys}
              node={child}
              onToggleNode={onToggleNode}
            />
          ))}
        </>
      )}
    </div>
  );
}

export function ProjectTodoCard({
  agentWorkStatusByWindowId,
  busy,
  clientId,
  compactTree = false,
  commentingTodoIds,
  dispatchErrors,
  dispatchingTodoIds,
  draggingTodoId,
  highlightedParentTodoId,
  mergeTargetTodoId,
  projectPath,
  registerTodoRef,
  selectedTodoId,
  todo,
  treeDepth = 0,
  onDragEnd,
  onDragStart,
  onMergeDragEnter,
  onMergeDragLeave,
  onMergeDragOver,
  onMergeDrop,
  onComment,
  onCreateChildTodo,
  onDispatch,
  onOpenTodo,
  onOpenTerminalWindow,
  onShowChildTodos,
  onRetryArtifact,
  onToggleSchedule,
  onUploadAttachment,
  retryingArtifactLinkId,
  uploadingAttachmentTodoIds,
}: ProjectTodoCardSharedProps & {
  compactTree?: boolean;
  todo: ProjectTodoListItem;
  treeDepth?: number;
}) {
  const { t } = useI18n();
  const created = formatProjectTodoShortDate(todo.created_at);
  const agent = projectTodoAssignee(todo);
  const terminalWindowId = todo.assigned_window_id;
  const agentWorkStatus = todo.assigned_terminal?.work_status
    ?? (terminalWindowId === null ? null : agentWorkStatusByWindowId.get(terminalWindowId) ?? null);
  const stageDispatching = projectTodoDispatchStageActive(todo);
  const dispatchTone = projectTodoDispatchTone(todo.dispatch_stage);
  const dispatchWaiting = todo.queued_dispatch && !stageDispatching;
  const dispatchTitle = projectTodoDispatchTitle(todo.dispatch_stage, todo.dispatch_error, t)
    ?? (dispatchWaiting ? t("projectTodo.dispatch.waiting") : null);
  const dispatchBusy = dispatchingTodoIds.has(todo.id) || stageDispatching;
  const dispatchErrorMessage = dispatchErrors[todo.id] ?? (todo.dispatch_stage === "FAILED" ? todo.dispatch_error : null);
  const canDispatch = todo.status === "TODO" && !dispatchWaiting;
  const canComment = todo.assigned_window_id !== null && !stageDispatching;
  const commentBusy = commentingTodoIds.has(todo.id);
  const uploadingAttachment = uploadingAttachmentTodoIds.has(todo.id);
  const terminal = todo.assigned_terminal;
  const terminalTags = projectTodoTerminalTags(todo);
  const scheduleBadges = projectTodoScheduleBadges(todo, t);
  const agentLabel = todo.agent_profile_id
    ? t("projectTodo.card.agentProfileLabel", { agent, profile: todo.agent_profile_id })
    : t("projectTodo.card.agentLabel", { agent });
  const todoTypeLabel = todo.todo_type.name.trim() || todo.todo_type.id;
  const tagLabels = [todo.agent_profile_id, ...scheduleBadges, ...terminalTags].filter((tag): tag is string => Boolean(tag));
  const visibleTagLabels = tagLabels.slice(0, 2);
  const mergeSource = terminal?.git_worktree ?? todo.implementation_worktree;
  const showBadges = gitMergeAttentionRequired(mergeSource);
  const className = [
    "project-todo-card",
    todo.review_unseen ? "review-unseen" : "",
    selectedTodoId === todo.id ? "selected" : "",
    highlightedParentTodoId === todo.id ? "child-filter-parent" : "",
    draggingTodoId === todo.id ? "dragging" : "",
    mergeTargetTodoId === todo.id ? "merge-target" : "",
    compactTree ? "tree-card" : ""
  ].filter(Boolean).join(" ");

  return (
    <article
      ref={(element) => registerTodoRef(todo.id, element)}
      data-debug-id="project-todo-card"
      data-project-todo-id={todo.id}
      className={className}
      draggable
      tabIndex={-1}
      style={compactTree ? ({ "--tree-depth": treeDepth } as CSSProperties) : undefined}
      onClick={(event) => {
        if (projectTodoCardEventTargetsNestedAction(event)) {
          return;
        }
        onOpenTodo(todo.id);
      }}
      onDragEnd={onDragEnd}
      onDragStart={(event) => {
        if (projectTodoCardEventTargetsNestedAction(event)) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }
        onDragStart(event, todo);
      }}
      onDragEnter={(event) => onMergeDragEnter(event, todo)}
      onDragLeave={(event) => onMergeDragLeave(event, todo)}
      onDragOver={(event) => onMergeDragOver(event, todo)}
      onDrop={(event) => onMergeDrop(event, todo)}
    >
      {todo.review_unseen && <span className="project-todo-review-unseen-dot" aria-hidden="true" />}
      <span className="project-todo-card-agent">
        <ProjectTodoAgentStatusIcon
          status={agentWorkStatus}
          terminalLinked={terminalWindowId !== null}
          dispatchActive={stageDispatching}
          dispatchTitle={dispatchTitle}
          dispatchTone={dispatchTone}
          label={agentLabel}
        />
      </span>
      <ProjectTodoCardArtifactStatus
        agentWorkStatusByWindowId={agentWorkStatusByWindowId}
        busy={busy}
        retryingArtifactLinkId={retryingArtifactLinkId}
        todo={todo}
        onRetryArtifact={onRetryArtifact}
      />
      <button
        type="button"
        className="project-todo-card-main"
        onClick={(event) => {
          event.stopPropagation();
          onOpenTodo(todo.id);
        }}
      >
        <span className="project-todo-card-path">{projectTodoTopicLabel(todo)}</span>
        <span className="project-todo-card-title-row">
          <span className="project-todo-drag-handle" aria-hidden="true" title={t("projectTodo.card.drag")}>::</span>
          {todo.parent_todo === null ? (
            <strong>
              <span>{todo.title}</span>
            </strong>
          ) : (
            <strong className="project-todo-card-title-stack">
              <span className="project-todo-card-child-title">{todo.title}</span>
              <small className="project-todo-card-parent-title">{todo.parent_todo.title}</small>
            </strong>
          )}
        </span>
        {showBadges && (
          <span className="project-todo-card-badges">
            <GitMergeStatusBadge source={mergeSource} compact />
          </span>
        )}
      </button>
      <span className="project-todo-card-type project-todo-type-pill">{todoTypeLabel}</span>
      {tagLabels.length > 0 && (
        <span className="project-todo-card-tags" title={tagLabels.join(", ")}>
          {visibleTagLabels.map((tag) => <span key={tag}>{tag}</span>)}
          {tagLabels.length > visibleTagLabels.length && <span aria-label={t("projectTodo.card.moreTags")}>...</span>}
        </span>
      )}
      {dispatchErrorMessage !== null && (
        <p className="project-todo-card-dispatch-error" role="alert">{dispatchErrorMessage}</p>
      )}
      <div className="project-todo-card-footer">
        {created ? (
          <span className="project-todo-card-meta">
            <time dateTime={todo.created_at}>{created}</time>
          </span>
        ) : null}
        <ProjectTodoScheduleToggle busy={busy} todo={todo} onToggleSchedule={onToggleSchedule} />
        <ProjectTodoAttachmentCount todo={todo} />
        <div className="project-todo-card-actions">
          <ProjectTodoCreateChildButton
            busy={busy}
            className="project-todo-card-action-button project-todo-create-child-button"
            todo={todo}
            onCreateChild={onCreateChildTodo}
          />
          {todo.status === "TODO" && (
            <ProjectTodoAttachmentUploadButton
              busy={busy}
              className="project-todo-card-action-button project-todo-attachment-upload-button"
              todo={todo}
              uploading={uploadingAttachment}
              onUpload={onUploadAttachment}
            />
          )}
          {todo.child_todos.length > 0 && (
            <button
              type="button"
              className="project-todo-card-action-button project-todo-children-filter-button"
              aria-label={t("projectTodo.action.showChildrenNamed", { title: todo.title })}
              title={t("projectTodo.action.showChildren")}
              onClick={(event) => {
                event.stopPropagation();
                onShowChildTodos(todo);
              }}
            >
              <UiIcon name="list-tree" />
            </button>
          )}
          {(canDispatch || dispatchBusy) && (
            <ProjectTodoCardDispatchButton
              busy={busy}
              dispatchBusy={dispatchBusy}
              dispatching={dispatchingTodoIds.has(todo.id)}
              dispatchTitle={dispatchTitle}
              dispatchTone={dispatchTone}
              todo={todo}
              onDispatch={onDispatch}
            />
          )}
          {terminalWindowId !== null && (
            <ProjectTodoCardAgentConversationButton
              clientId={clientId}
              projectPath={projectPath}
              terminal={terminal}
              todo={todo}
              windowId={terminalWindowId}
            />
          )}
          {(canComment || commentBusy) && (
            <button
              type="button"
              className="project-todo-card-action-button project-todo-comment-button"
              aria-label={commentBusy ? t("projectTodo.action.sendingCommentNamed", { title: todo.title }) : t("projectTodo.action.commentNamed", { title: todo.title })}
              title={t("projectTodo.action.comment")}
              disabled={busy || commentBusy}
              onClick={(event) => {
                event.stopPropagation();
                onComment(todo);
              }}
            >
              {commentBusy ? (
                <span className="terminal-create-progress-spinner project-todo-card-action-spinner blue" aria-hidden="true" />
              ) : (
                <CommentIcon />
              )}
            </button>
          )}
          {terminalWindowId !== null && (
            <button
              type="button"
              className="project-todo-card-action-button project-todo-terminal-button"
              aria-label={t("projectTodo.action.openTerminalNamed", { title: todo.title })}
              title={t("projectTodo.action.openTerminal")}
              onClick={(event) => {
                event.stopPropagation();
                onOpenTerminalWindow(terminalWindowId, projectPath, terminal?.title ?? todo.title);
              }}
            >
              <TerminalIcon />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function projectTodoScheduleBadges(todo: ProjectTodoListItem, t: TranslateFn): string[] {
  if (todo.execution_kind !== "PERIODIC") {
    return [];
  }
  const badges = [t("projectTodo.schedule.periodic")];
  badges.push(todo.terminal_policy === "REUSE_LATEST" ? t("projectTodo.schedule.reuseTerminal") : t("projectTodo.schedule.newTerminal"));
  if (todo.trigger_strategy === "CRON" && todo.cron_expression !== null) {
    badges.push(todo.cron_expression);
  }
  return badges;
}

function projectTodoCardEventTargetsNestedAction(event: MouseEvent<HTMLElement> | DragEvent<HTMLElement>): boolean {
  const target = event.target;
  if (!(target instanceof Element)) {
    return false;
  }
  return target.closest(
    "button,input,select,textarea,a,label,[role='button']"
  ) !== null;
}

function ProjectTodoCardDispatchButton({
  busy,
  dispatchBusy,
  dispatching,
  dispatchTitle,
  dispatchTone,
  todo,
  onDispatch
}: {
  busy: boolean;
  dispatchBusy: boolean;
  dispatching: boolean;
  dispatchTitle: string | null;
  dispatchTone: ProjectTodoDispatchTone | null;
  todo: ProjectTodoListItem;
  onDispatch: (todo: ProjectTodoListItem) => void;
}) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      className="project-todo-card-action-button project-todo-dispatch-button"
      aria-label={dispatchBusy
        ? t("projectTodo.action.dispatchingNamed", { title: todo.title })
        : t("projectTodo.action.dispatchNamed", { title: todo.title })}
      title={dispatchTitle ?? (dispatching ? t("projectTodo.action.dispatching") : t("projectTodo.action.dispatch"))}
      disabled={busy || dispatchBusy}
      onClick={(event) => {
        event.stopPropagation();
        onDispatch(todo);
      }}
    >
      {dispatchBusy ? (
        <span
          className={`terminal-create-progress-spinner project-todo-card-action-spinner ${dispatchTone ?? "blue"}`}
          aria-hidden="true"
        />
      ) : (
        <DispatchIcon />
      )}
    </button>
  );
}

function ChevronIcon({
  collapsed,
  muted = false
}: {
  collapsed: boolean;
  muted?: boolean;
}) {
  return (
    <svg
      className={muted ? "muted" : ""}
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {collapsed ? <path d="m9 6 6 6-6 6" /> : <path d="m6 9 6 6 6-6" />}
    </svg>
  );
}

function DispatchIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h11" />
      <path d="m12 6 6 6-6 6" />
    </svg>
  );
}

function CommentIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M7 8h10" />
      <path d="M7 12h6" />
      <path d="M5 19l3-3h11a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2" />
    </svg>
  );
}

function TerminalIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 5h16v11H4z" />
      <path d="m8 9 3 3-3 3" />
      <path d="M13 15h4" />
      <path d="M8 20h8" />
    </svg>
  );
}
