import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchProjectReviewConfig, updateProjectReviewConfig } from "../api";
import { useI18n } from "../i18n";
import type {
  ProjectReviewConfig,
  ProjectReviewMergePolicy,
  ProjectReviewProvider
} from "../types";

type ProjectReviewSettingsProps = {
  clientId: string;
  projectPath: string;
};

function queryKey(clientId: string, projectPath: string) {
  return ["project-review-config", clientId, projectPath] as const;
}

function artifactKindsText(config: ProjectReviewConfig | null): string {
  return config?.required_artifact_kinds.join(", ") ?? "";
}

function parseArtifactKinds(value: string): string[] {
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

export function ProjectReviewSettings({ clientId, projectPath }: ProjectReviewSettingsProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const configQuery = useQuery({
    queryKey: queryKey(clientId, projectPath),
    queryFn: () => fetchProjectReviewConfig(clientId, projectPath),
    refetchInterval: 10000
  });
  const config = configQuery.data ?? null;
  const [provider, setProvider] = useState<ProjectReviewProvider>("LOCAL_CARD");
  const [reviewAgent, setReviewAgent] = useState("");
  const [reviewCommand, setReviewCommand] = useState("");
  const [reviewProfileId, setReviewProfileId] = useState("");
  const [autoCreateTarget, setAutoCreateTarget] = useState(true);
  const [autoDispatchReview, setAutoDispatchReview] = useState(false);
  const [mergePolicy, setMergePolicy] = useState<ProjectReviewMergePolicy>("MANUAL");
  const [artifactKinds, setArtifactKinds] = useState("");

  useEffect(() => {
    if (config === null) {
      return;
    }
    setProvider(config.pr_provider);
    setReviewAgent(config.review_agent ?? "");
    setReviewCommand(config.review_agent_command ?? "");
    setReviewProfileId(config.review_agent_profile_id ?? "");
    setAutoCreateTarget(config.auto_create_review_target);
    setAutoDispatchReview(config.auto_dispatch_review);
    setMergePolicy(config.merge_policy);
    setArtifactKinds(artifactKindsText(config));
  }, [config]);

  const draftChanged = useMemo(() => {
    if (config === null) {
      return false;
    }
    return provider !== config.pr_provider
      || reviewAgent.trim() !== (config.review_agent ?? "")
      || reviewCommand.trim() !== (config.review_agent_command ?? "")
      || reviewProfileId.trim() !== (config.review_agent_profile_id ?? "")
      || autoCreateTarget !== config.auto_create_review_target
      || autoDispatchReview !== config.auto_dispatch_review
      || mergePolicy !== config.merge_policy
      || artifactKinds.trim() !== artifactKindsText(config);
  }, [
    artifactKinds,
    autoCreateTarget,
    autoDispatchReview,
    config,
    mergePolicy,
    provider,
    reviewAgent,
    reviewCommand,
    reviewProfileId
  ]);

  const saveMutation = useMutation({
    mutationFn: () => updateProjectReviewConfig(clientId, projectPath, {
      pr_provider: provider,
      review_agent: reviewAgent.trim() || null,
      review_agent_command: reviewCommand.trim() || null,
      review_agent_profile_id: reviewProfileId.trim() || null,
      auto_create_review_target: autoCreateTarget,
      auto_dispatch_review: autoDispatchReview,
      merge_policy: mergePolicy,
      required_artifact_kinds: parseArtifactKinds(artifactKinds)
    }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKey(clientId, projectPath), saved);
      void queryClient.invalidateQueries({ queryKey: ["project-todos", clientId, projectPath] });
    }
  });

  if (configQuery.isError) {
    return <p className="error" role="alert">{t("project.review.loadFailed")}</p>;
  }

  return (
    <section className="detail-section project-review-settings" aria-label={t("project.review.config")}>
      <h3>{t("project.review.title")}</h3>
      <div className="project-review-settings-grid">
        <label className="settings-field">
          <span>{t("project.review.provider")}</span>
          <select value={provider} onChange={(event) => setProvider(event.target.value as ProjectReviewProvider)}>
            <option value="LOCAL_CARD">{t("project.review.localCard")}</option>
            <option value="GITEA">Gitea</option>
            <option value="GITHUB">GitHub</option>
          </select>
        </label>
        <label className="settings-field">
          <span>{t("project.review.agent")}</span>
          <input value={reviewAgent} onChange={(event) => setReviewAgent(event.target.value)} placeholder="codex" />
        </label>
        <label className="settings-field">
          <span>{t("project.review.agentCommand")}</span>
          <input value={reviewCommand} onChange={(event) => setReviewCommand(event.target.value)} placeholder="codex" />
        </label>
        <label className="settings-field">
          <span>{t("project.review.profileId")}</span>
          <input value={reviewProfileId} onChange={(event) => setReviewProfileId(event.target.value)} placeholder="builtin/pr-review" />
        </label>
        <label className="settings-field">
          <span>{t("project.review.mergePolicy")}</span>
          <select value={mergePolicy} onChange={(event) => setMergePolicy(event.target.value as ProjectReviewMergePolicy)}>
            <option value="MANUAL">{t("project.review.mergeManual")}</option>
            <option value="AUTO_AFTER_PASSED">{t("project.review.mergeAutoAfterPassed")}</option>
          </select>
        </label>
        <label className="settings-field">
          <span>{t("project.review.requiredArtifacts")}</span>
          <input value={artifactKinds} onChange={(event) => setArtifactKinds(event.target.value)} placeholder="review_report, test_report" />
        </label>
      </div>
      <div className="project-review-settings-toggles">
        <label className="settings-field settings-field-checkbox">
          <span>{t("project.review.createTarget")}</span>
          <input type="checkbox" checked={autoCreateTarget} onChange={(event) => setAutoCreateTarget(event.target.checked)} />
        </label>
        <label className="settings-field settings-field-checkbox">
          <span>{t("project.review.autoDispatch")}</span>
          <input type="checkbox" checked={autoDispatchReview} onChange={(event) => setAutoDispatchReview(event.target.checked)} />
        </label>
      </div>
      <div className="project-review-settings-actions">
        {configQuery.isLoading && <span className="muted">{t("common.loading")}</span>}
        {saveMutation.isError && <span className="error" role="alert">{t("project.review.saveFailed")}</span>}
        <button
          type="button"
          disabled={config === null || !draftChanged || saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          {t("project.review.save")}
        </button>
      </div>
    </section>
  );
}
