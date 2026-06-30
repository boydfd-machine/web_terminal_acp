import { isActiveTerminalArtifact } from "../artifactTerminalCarrier";
import { artifactModelDefaultSelection } from "../artifactModelSelection";
import type { ArtifactProjectTodoCreateInput } from "../artifactProjectTodoBridge";
import { useI18n, type TranslateFn } from "../i18n";
import type {
  AgentLaunchKind,
  AgentModelSelection,
  ArtifactListItem,
  ArtifactScope,
  PageReviewCard,
  PageReviewCardsArtifactContent,
  ProjectTodo,
  TerminalArtifact
} from "../types";
import { ArtifactModelSelectionField } from "./ArtifactModelSelectionField";
import { ArtifactProjectTodoFrame } from "./ArtifactProjectTodoFrame";
import { UiIcon } from "./UiIcon";
import { artifactKindLabel, artifactStatusLabel } from "./windowDetailData";

type CreatingPageReviewTodo = { artifactId: string; cardId: string } | null;

type WindowArtifactsPanelProps = {
  artifactFullscreen: boolean;
  artifactPage: number;
  artifactScope: ArtifactScope;
  artifactItems: ArtifactListItem[];
  artifactsData: { offset: number; has_more: boolean } | null | undefined;
  artifactsError: boolean;
  artifactsFetching: boolean;
  artifactsLoading: boolean;
  clientId: string;
  createArtifactError: unknown;
  createArtifactPending: boolean;
  createPageReviewTodoError: unknown;
  creatingPageReviewTodo: CreatingPageReviewTodo;
  itemWindowId: string;
  artifactModelAgent: AgentLaunchKind | null;
  projectPath: string | null;
  artifactModelSelection: AgentModelSelection | null;
  selectedItem: ArtifactListItem | null;
  selectedItemCanDisplay: boolean;
  selectedItemId: string | null;
  selectedItemReady: boolean;
  selectedItemSrcDoc: string | null;
  selectedItemHtmlError: boolean;
  windowId: string;
  onArtifactScopeChange: (scope: ArtifactScope) => void;
  onCreateArtifact: (
    clientId: string,
    windowId: string,
    artifactKind: string,
    artifactScope: ArtifactScope,
    artifactModelSelection: AgentModelSelection | null
  ) => void;
  onCreateProjectTodoFromArtifact?: (
    card: ArtifactProjectTodoCreateInput,
    artifactId: string | null
  ) => Promise<ProjectTodo>;
  onCreatePageReviewTodo: (artifact: TerminalArtifact, cardId: string) => void;
  onOpenArtifactTerminal?: (artifact: TerminalArtifact) => void;
  onArtifactModelSelectionChange: (value: AgentModelSelection | null) => void;
  setArtifactFullscreen: (value: boolean) => void;
  setArtifactPage: (updater: (page: number) => number) => void;
  setSelectedItemId: (id: string) => void;
};

export function WindowArtifactsPanel({
  artifactFullscreen,
  artifactPage,
  artifactScope,
  artifactItems,
  artifactsData,
  artifactsError,
  artifactsFetching,
  artifactsLoading,
  clientId,
  createArtifactError,
  createArtifactPending,
  createPageReviewTodoError,
  creatingPageReviewTodo,
  itemWindowId,
  artifactModelAgent,
  projectPath,
  artifactModelSelection,
  selectedItem,
  selectedItemCanDisplay,
  selectedItemId,
  selectedItemReady,
  selectedItemSrcDoc,
  selectedItemHtmlError,
  windowId,
  onArtifactScopeChange,
  onCreateArtifact,
  onCreateProjectTodoFromArtifact,
  onCreatePageReviewTodo,
  onOpenArtifactTerminal,
  onArtifactModelSelectionChange,
  setArtifactFullscreen,
  setArtifactPage,
  setSelectedItemId
}: WindowArtifactsPanelProps) {
  const { t } = useI18n();
  const selectedArtifact = selectedItem?.kind === "terminal_artifact" ? selectedItem.artifact : null;
  const selectedPreview = selectedItem?.kind === "plugin_preview" ? selectedItem.preview : null;
  const selectedArtifactHasPageReviewCards = selectedArtifact !== null && pageReviewCardsContent(selectedArtifact) !== null;
  const projectScopeUnavailable = artifactScope === "project" && projectPath === null;
  const effectiveArtifactModelSelection = artifactModelSelection ?? artifactModelDefaultSelection(artifactModelAgent);
  const artifactScopeLabel = artifactScope === "terminal"
    ? t("artifacts.scope.terminal")
    : t("artifacts.scope.project");
  return (
    <div className="artifact-panel" data-debug-id="artifact-panel">
      <div className="artifact-scope-tabs" role="tablist" aria-label={t("artifacts.scope")}>
        <button
          type="button"
          role="tab"
          aria-selected={artifactScope === "terminal"}
          className={artifactScope === "terminal" ? "selected" : undefined}
          onClick={() => onArtifactScopeChange("terminal")}
        >
          {t("artifacts.scope.terminal")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={artifactScope === "project"}
          className={artifactScope === "project" ? "selected" : undefined}
          onClick={() => onArtifactScopeChange("project")}
        >
          {t("artifacts.scope.project")}
        </button>
      </div>
      <div className="artifact-toolbar">
        <ArtifactModelSelectionField
          agent={artifactModelAgent}
          className="artifact-toolbar-model"
          value={artifactModelSelection}
          onChange={onArtifactModelSelectionChange}
        />
        {artifactScope === "terminal" ? (
          <>
            <button
              type="button"
              disabled={createArtifactPending}
              onClick={() => onCreateArtifact(clientId, itemWindowId, "agent_trace_graph", "terminal", effectiveArtifactModelSelection)}
            >
              {t("artifacts.generateTrace")}
            </button>
            <button
              type="button"
              disabled={createArtifactPending}
              onClick={() => onCreateArtifact(clientId, itemWindowId, "agent_pitfalls", "terminal", effectiveArtifactModelSelection)}
            >
              {t("artifacts.generatePitfalls")}
            </button>
            <button
              type="button"
              disabled={createArtifactPending}
              onClick={() => onCreateArtifact(clientId, itemWindowId, "page_review_cards", "terminal", effectiveArtifactModelSelection)}
            >
              {t("artifacts.generatePageReview")}
            </button>
          </>
        ) : (
          <button
            type="button"
            disabled={createArtifactPending || projectPath === null}
            onClick={() => onCreateArtifact(clientId, itemWindowId, "user_journey", "project", effectiveArtifactModelSelection)}
          >
            {t("artifacts.generateUserJourney")}
          </button>
        )}
        {selectedItemCanDisplay && (
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("artifacts.openFullscreen")}
            title={t("artifacts.fullscreen")}
            onClick={() => setArtifactFullscreen(true)}
          >
            <UiIcon name="maximize" />
          </button>
        )}
      </div>
      {projectScopeUnavailable && (
        <p className="muted">{t("artifacts.projectRequired")}</p>
      )}
      {createArtifactError !== null && (
        <p className="error" role="alert">
          {createArtifactError instanceof Error ? createArtifactError.message : t("artifacts.createFailed")}
        </p>
      )}
      {createPageReviewTodoError !== null && (
        <p className="error" role="alert">
          {createPageReviewTodoError instanceof Error ? createPageReviewTodoError.message : t("artifacts.addTodoFailed")}
        </p>
      )}
      {artifactsLoading && <p className="muted">{t("artifacts.loading")}</p>}
      {artifactsError && <p className="error" role="alert">{t("artifacts.loadFailed")}</p>}
      {!artifactsLoading && !artifactsError && artifactItems.length === 0 && !projectScopeUnavailable && (
        <p className="muted">{t("artifacts.empty")}</p>
      )}
      {artifactItems.length > 0 && (
        <div className="artifact-browser">
          <div className="artifact-list" data-debug-id="artifact-list" role="listbox" aria-label={`${artifactScopeLabel} ${t("artifacts.title")}`}>
            {artifactItems.map((item) => (
              <button
                key={item.id}
                type="button"
                data-debug-id="artifact-card"
                data-artifact-id={item.id}
                role="option"
                aria-selected={item.id === selectedItemId}
                className={item.id === selectedItemId ? "selected" : undefined}
                onClick={() => {
                  setSelectedItemId(item.id);
                  if (item.kind === "terminal_artifact" && isActiveTerminalArtifact(item.artifact)) {
                    onOpenArtifactTerminal?.(item.artifact);
                  }
                }}
              >
                <strong>{itemTitle(item, t)}</strong>
                <span>{itemKindLabel(item, t)}</span>
                <small className={`artifact-status ${itemStatusClass(item)}`}>{itemStatusLabel(item, t)}</small>
              </button>
            ))}
          </div>
          <div className={selectedArtifactHasPageReviewCards ? "artifact-preview page-review" : "artifact-preview"}>
            {selectedItem === null ? (
              <p className="muted">{t("artifacts.select")}</p>
            ) : selectedArtifact !== null && selectedArtifact.status.toUpperCase() === "FAILED" ? (
              <p className="error" role="alert">{selectedArtifact.last_error ?? t("artifacts.generationFailed")}</p>
            ) : selectedPreview !== null && selectedPreview.status !== "valid" ? (
              <p className="error" role="alert">{selectedPreview.last_error ?? t("artifacts.previewInvalid")}</p>
            ) : selectedItemReady && selectedItemHtmlError ? (
              <p className="error" role="alert">{t("artifacts.previewFailed")}</p>
            ) : selectedItemReady && selectedItemSrcDoc ? (
              <>
                {selectedArtifact !== null && (
                  <PageReviewTodoCards
                    artifact={selectedArtifact}
                    creatingPageReviewTodo={creatingPageReviewTodo}
                    projectPath={projectPath}
                    onCreateTodo={onCreatePageReviewTodo}
                  />
                )}
                <ArtifactProjectTodoFrame
                  artifactId={selectedArtifact?.id ?? null}
                  clientId={clientId}
                  projectPath={projectPath}
                  srcDoc={selectedItemSrcDoc}
                  title={itemTitle(selectedItem, t)}
                  onCreateProjectTodo={onCreateProjectTodoFromArtifact}
                />
              </>
            ) : selectedItemReady ? (
              <p className="muted">{t("artifacts.previewLoading")}</p>
            ) : (
              <p className="muted">{itemStatusLabel(selectedItem, t)}...</p>
            )}
          </div>
        </div>
      )}
      {artifactsData && (artifactsData.offset > 0 || artifactsData.has_more) && (
        <div className="detail-pagination">
          <button
            type="button"
            className="ui-icon-button"
            disabled={artifactPage === 0 || artifactsFetching}
            aria-label={t("artifacts.previousPage")}
            title={t("common.previous")}
            onClick={() => setArtifactPage((page) => Math.max(0, page - 1))}
          >
            <UiIcon name="chevron-left" />
          </button>
          <button
            type="button"
            className="ui-icon-button"
            disabled={!artifactsData.has_more || artifactsFetching}
            aria-label={t("artifacts.nextPage")}
            title={t("common.next")}
            onClick={() => setArtifactPage((page) => page + 1)}
          >
            <UiIcon name="chevron-right" />
          </button>
        </div>
      )}
      {artifactFullscreen && selectedItemCanDisplay && selectedItem !== null && selectedItemSrcDoc !== null && (
        <div className="artifact-fullscreen" role="dialog" aria-modal="true" aria-label={t("artifacts.terminalArtifact")}>
          <button type="button" className="artifact-fullscreen-backdrop" aria-label={t("artifacts.closeArtifact")} onClick={() => setArtifactFullscreen(false)} />
          <section className="artifact-fullscreen-panel">
            <header>
              <strong>{itemTitle(selectedItem, t)}</strong>
              <button
                type="button"
                className="ui-icon-button"
                aria-label={t("artifacts.closeArtifact")}
                title={t("common.close")}
                onClick={() => setArtifactFullscreen(false)}
              >
                <UiIcon name="x" />
              </button>
            </header>
            <ArtifactProjectTodoFrame
              artifactId={selectedArtifact?.id ?? null}
              clientId={clientId}
              projectPath={projectPath}
              srcDoc={selectedItemSrcDoc}
              title={itemTitle(selectedItem, t)}
              onCreateProjectTodo={onCreateProjectTodoFromArtifact}
            />
          </section>
        </div>
      )}
    </div>
  );
}

function itemTitle(item: ArtifactListItem, t: TranslateFn): string {
  if (item.kind === "terminal_artifact") {
    return item.artifact.title;
  }
  const label = item.preview.draft_artifact_kind ?? t("common.none");
  return t("artifacts.draftPreview", { label });
}

function itemKindLabel(item: ArtifactListItem, t: TranslateFn): string {
  return item.kind === "terminal_artifact"
    ? artifactKindLabel(item.artifact.artifact_kind, t)
    : t("artifacts.pluginPreview");
}

function itemStatusLabel(item: ArtifactListItem, t: TranslateFn): string {
  return item.kind === "terminal_artifact"
    ? artifactStatusLabel(item.artifact, t)
    : item.preview.status;
}

function itemStatusClass(item: ArtifactListItem): string {
  return item.kind === "terminal_artifact"
    ? item.artifact.status.toLowerCase()
    : item.preview.status;
}

function PageReviewTodoCards({
  artifact,
  creatingPageReviewTodo,
  projectPath,
  onCreateTodo
}: {
  artifact: TerminalArtifact;
  creatingPageReviewTodo: CreatingPageReviewTodo;
  projectPath: string | null;
  onCreateTodo: (artifact: TerminalArtifact, cardId: string) => void;
}) {
  const { t } = useI18n();
  const content = pageReviewCardsContent(artifact);
  if (content === null) {
    return null;
  }
  return (
    <div className="artifact-page-review-cards" aria-label={t("artifacts.pageReviewCards")}>
      {content.cards.map((card) => {
        const pending = creatingPageReviewTodo?.artifactId === artifact.id && creatingPageReviewTodo.cardId === card.id;
        return (
          <article key={card.id} className="artifact-page-review-card">
            <div className="artifact-page-review-card-meta">
              <span>{card.priority}</span>
              <span>{card.severity}</span>
              <span>{card.type}</span>
            </div>
            <strong>{card.title}</strong>
            <p>{card.proposal || card.problem}</p>
            <button
              type="button"
              disabled={pending || projectPath === null}
              title={projectPath === null ? t("artifacts.projectPathRequired") : undefined}
              onClick={() => onCreateTodo(artifact, card.id)}
            >
              {pending ? t("artifacts.addingTodo") : t("artifacts.addTodo")}
            </button>
          </article>
        );
      })}
    </div>
  );
}

function pageReviewCardsContent(artifact: TerminalArtifact): PageReviewCardsArtifactContent | null {
  if (artifact.artifact_kind !== "page_review_cards" || artifact.content_json === null) {
    return null;
  }
  const value = artifact.content_json;
  const cards = Array.isArray(value.cards) ? value.cards.map(pageReviewCard).filter(isPageReviewCard) : [];
  if (cards.length === 0) {
    return null;
  }
  return {
    artifact_kind: "page_review_cards",
    title: textValue(value.title) || artifact.title,
    page: textValue(value.page) || "Current page or flow",
    review_scope: textValue(value.review_scope),
    executive_summary: textValue(value.executive_summary),
    cards
  };
}

function pageReviewCard(value: unknown): PageReviewCard | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = textValue(record.id);
  const title = textValue(record.title);
  if (!id || !title) {
    return null;
  }
  return {
    id,
    title,
    type: textValue(record.type) || "enhancement",
    priority: textValue(record.priority) || "P2",
    severity: textValue(record.severity) || "medium",
    user_value: textValue(record.user_value),
    problem: textValue(record.problem),
    proposal: textValue(record.proposal),
    evidence: [],
    acceptance_criteria: [],
    test_notes: []
  };
}

function isPageReviewCard(value: PageReviewCard | null): value is PageReviewCard {
  return value !== null;
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
