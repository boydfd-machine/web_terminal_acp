import { useMemo, useState, type ChangeEvent, type DragEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteSystemAgentConfigItem,
  downloadSystemSkill,
  fetchSystemAgentConfig,
  resetSystemAgentConfigItem,
  updateSystemAgentConfigItem,
  uploadSystemSkill,
  upsertSystemMcpServer
} from "../../api";
import { useApiFailureToast } from "../../AppQueryErrorBridge";
import type { AgentConfig, AgentConfigSection } from "../../types";
import { SystemAgentConfigDetail } from "../../components/SystemAgentConfigDetail";
import { useI18n } from "../../i18n";
import { SystemConfigList, type SystemConfigSectionId, type SystemStatus } from "./SystemConfigList";

type SystemConfigView = "system-skills" | "system-plugins" | "system-mcp";

function configSection(config: AgentConfig | null | undefined, sectionId: AgentConfigSection["id"]): AgentConfigSection {
  return config?.sections.find((section) => section.id === sectionId) ?? {
    id: sectionId,
    name: sectionId,
    items: []
  };
}

function suggestedSkillId(file: File | null): string {
  if (file === null) {
    return "";
  }
  return file.name.replace(/\.zip$/i, "").trim();
}

function systemItemKey(sectionId: string, itemId: string): string {
  return `${sectionId}:${itemId}`;
}

function detailQueryKey(sectionId: SystemConfigSectionId): string | null {
  if (sectionId === "skills") {
    return "system-skill-detail";
  }
  if (sectionId === "mcp") {
    return "system-mcp-detail";
  }
  return null;
}

function activeSectionForView(view: SystemConfigView): SystemConfigSectionId {
  if (view === "system-skills") {
    return "skills";
  }
  if (view === "system-plugins") {
    return "plugins";
  }
  return "mcp";
}

function errorStatus(error: unknown, fallback: string): SystemStatus {
  return { kind: "error", message: error instanceof Error ? error.message : fallback };
}

function SystemUploadIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="system-config-upload-icon">
      <path d="M12 15V4" />
      <path d="m7.5 8.5 4.5-4.5 4.5 4.5" />
      <path d="M5 15v2.5A2.5 2.5 0 0 0 7.5 20h9A2.5 2.5 0 0 0 19 17.5V15" />
    </svg>
  );
}

function SystemSaveIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="system-config-button-icon">
      <path d="M6 3h10l3 3v15H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M8 3v6h8" />
      <path d="M8 17h8" />
    </svg>
  );
}

export function SystemAgentConfigSettings({ view }: { view: SystemConfigView }) {
  const { t } = useI18n();
  const showApiFailureToast = useApiFailureToast();
  const queryClient = useQueryClient();
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [skillFile, setSkillFile] = useState<File | null>(null);
  const [skillInputKey, setSkillInputKey] = useState(0);
  const [skillId, setSkillId] = useState("");
  const [mcpId, setMcpId] = useState("");
  const [mcpJson, setMcpJson] = useState("{\n  \"type\": \"stdio\",\n  \"command\": \"echo\"\n}");
  const [mcpEnabled, setMcpEnabled] = useState(true);
  const [selected, setSelected] = useState<{ sectionId: SystemConfigSectionId; itemId: string } | null>(null);

  const configQuery = useQuery({
    queryKey: ["system-agent-config"],
    queryFn: fetchSystemAgentConfig
  });
  const config = configQuery.data ?? null;
  const skillsSection = useMemo(() => configSection(config, "skills"), [config]);
  const pluginsSection = useMemo(() => configSection(config, "plugins"), [config]);
  const mcpSection = useMemo(() => configSection(config, "mcp"), [config]);
  const activeSectionId = activeSectionForView(view);
  const selectedItemId = selected?.sectionId === activeSectionId ? selected.itemId : null;

  const setConfig = (nextConfig: AgentConfig) => {
    queryClient.setQueryData(["system-agent-config"], nextConfig);
    void queryClient.invalidateQueries({ queryKey: ["client-system-agent-config"] });
    void queryClient.invalidateQueries({ queryKey: ["client-agent-config"] });
    void queryClient.invalidateQueries({ queryKey: ["agent-profile-config"] });
  };
  const toggleMutation = useMutation({
    mutationFn: (input: { sectionId: SystemConfigSectionId; itemId: string; enabled: boolean }) =>
      updateSystemAgentConfigItem(input.sectionId, input.itemId, input.enabled),
    onMutate: (input) => {
      setStatus(null);
      setPendingKey(systemItemKey(input.sectionId, input.itemId));
    },
    onSuccess: (nextConfig, input) => {
      setConfig(nextConfig);
      const queryKey = detailQueryKey(input.sectionId);
      if (queryKey !== null) {
        void queryClient.invalidateQueries({ queryKey: [queryKey, input.itemId] });
      }
    },
    onError: (error) => setStatus(errorStatus(error, t("settings.system.updateFailed"))),
    onSettled: () => setPendingKey(null)
  });
  const deleteMutation = useMutation({
    mutationFn: (input: { sectionId: SystemConfigSectionId; itemId: string }) =>
      deleteSystemAgentConfigItem(input.sectionId, input.itemId),
    onMutate: (input) => {
      setStatus(null);
      setPendingKey(systemItemKey(input.sectionId, input.itemId));
    },
    onSuccess: setConfig,
    onError: (error) => setStatus(errorStatus(error, t("settings.system.deleteFailed"))),
    onSettled: () => setPendingKey(null)
  });
  const resetMutation = useMutation({
    mutationFn: (input: { sectionId: SystemConfigSectionId; itemId: string }) =>
      resetSystemAgentConfigItem(input.sectionId, input.itemId),
    onMutate: (input) => {
      setStatus(null);
      setPendingKey(systemItemKey(input.sectionId, input.itemId));
    },
    onSuccess: (nextConfig, input) => {
      setConfig(nextConfig);
      const queryKey = detailQueryKey(input.sectionId);
      if (queryKey !== null) {
        void queryClient.invalidateQueries({ queryKey: [queryKey, input.itemId] });
      }
      setStatus({ kind: "info", message: t("settings.system.resetDone") });
    },
    onError: (error) => setStatus(errorStatus(error, t("settings.system.resetFailed"))),
    onSettled: () => setPendingKey(null)
  });
  const uploadMutation = useMutation({
    mutationFn: (input: { skillId: string; file: File }) => uploadSystemSkill(input.skillId, input.file),
    onSuccess: (nextConfig) => {
      setConfig(nextConfig);
      setStatus({ kind: "info", message: t("settings.system.uploaded") });
      setSkillFile(null);
      setSkillInputKey((current) => current + 1);
      setSkillId("");
    },
    onError: (error) => setStatus(errorStatus(error, t("settings.system.uploadFailed")))
  });
  const mcpMutation = useMutation({
    mutationFn: (input: { id: string; server: Record<string, unknown>; enabled: boolean }) =>
      upsertSystemMcpServer(input),
    onSuccess: (nextConfig) => {
      setConfig(nextConfig);
      setStatus({ kind: "info", message: t("settings.system.savedMcp") });
      setMcpId("");
    },
    onError: (error) => setStatus(errorStatus(error, t("settings.system.saveFailed")))
  });

  const updateSkillFile = (file: File | null) => {
    setSkillFile(file);
    if (skillId.trim() === "") {
      setSkillId(suggestedSkillId(file));
    }
  };
  const onSkillFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    updateSkillFile(event.target.files?.[0] ?? null);
  };
  const onSkillFileDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    updateSkillFile(event.dataTransfer.files.item(0));
  };
  const uploadSkill = () => {
    if (skillFile === null || skillId.trim() === "") {
      return;
    }
    setStatus(null);
    uploadMutation.mutate({ skillId: skillId.trim(), file: skillFile });
  };
  const saveMcp = () => {
    try {
      const server = JSON.parse(mcpJson) as unknown;
      if (typeof server !== "object" || server === null || Array.isArray(server)) {
        setStatus({ kind: "error", message: t("settings.system.mcpObjectRequired") });
        return;
      }
      setStatus(null);
      mcpMutation.mutate({ id: mcpId.trim(), server: server as Record<string, unknown>, enabled: mcpEnabled });
    } catch {
      setStatus({ kind: "error", message: t("settings.system.mcpInvalidJson") });
    }
  };
  const onToggle = (sectionId: SystemConfigSectionId, itemId: string, enabled: boolean) => {
    toggleMutation.mutate({ sectionId, itemId, enabled });
  };
  const onDelete = (sectionId: SystemConfigSectionId, itemId: string) => {
    deleteMutation.mutate({ sectionId, itemId });
    setSelected((current) => (
      current?.sectionId === sectionId && current.itemId === itemId ? null : current
    ));
  };
  const onReset = (sectionId: SystemConfigSectionId, itemId: string) => {
    resetMutation.mutate({ sectionId, itemId });
  };
  const onSelect = (sectionId: SystemConfigSectionId, itemId: string) => {
    setStatus(null);
    setSelected({ sectionId, itemId });
  };
  const downloadSkill = async (itemId: string) => {
    try {
      setStatus(null);
      const archive = await downloadSystemSkill(itemId);
      const url = URL.createObjectURL(archive);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${itemId}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      showApiFailureToast(error);
      setStatus(errorStatus(error, t("settings.system.downloadFailed")));
    }
  };

  if (configQuery.isLoading) {
    return <p className="muted">{t("settings.system.loading")}</p>;
  }
  if (configQuery.isError) {
    return <p className="error" role="alert">{t("settings.system.loadFailed")}</p>;
  }

  if (view === "system-skills") {
    return (
    <section className="system-config-page">
      <SystemConfigList
        emptyMessage={t("settings.system.emptySkills")}
        items={skillsSection.items}
        pendingKey={pendingKey}
        selectedItemId={selectedItemId}
        sectionId="skills"
        status={status}
        title={t("settings.tab.systemSkills")}
        onSelect={onSelect}
        onToggle={onToggle}
        onDelete={onDelete}
        onDownload={downloadSkill}
      >
        <div className="system-config-editor system-config-sidebar-form">
          <div className="system-config-editor-header">
            <span>{t("settings.system.uploadSkill")}</span>
            <small>{t("settings.system.uploadSkillHint")}</small>
          </div>
          <label className="settings-field">
            <span>Skill ID</span>
            <input value={skillId} onChange={(event) => setSkillId(event.target.value)} placeholder="review-helper" />
          </label>
          <label
            className="system-config-upload"
            onDragOver={(event) => event.preventDefault()}
            onDrop={onSkillFileDrop}
          >
            <input
              key={skillInputKey}
              type="file"
              accept=".zip,application/zip"
              onChange={onSkillFileChange}
            />
            <SystemUploadIcon />
            <span className="system-config-upload-copy">
              <strong>{skillFile?.name ?? t("settings.system.skillZip")}</strong>
              <small>{skillFile === null ? t("settings.system.skillZipEmpty") : t("settings.system.skillZipSelected")}</small>
            </span>
          </label>
          <div className="settings-actions">
            <button
              type="button"
              className="system-config-primary-button"
              disabled={skillFile === null || skillId.trim() === "" || uploadMutation.isPending}
              onClick={uploadSkill}
            >
              <SystemUploadIcon />
              {t("settings.system.uploadSkill")}
            </button>
          </div>
        </div>
      </SystemConfigList>
      <main className="system-config-main">
        {selectedItemId === null ? (
          <SystemConfigEmptyDetail message={t("settings.system.selectSkillDetail")} />
        ) : (
          <SystemAgentConfigDetail
            sectionId="skills"
            itemId={selectedItemId}
            onConfigChange={setConfig}
            onReset={onReset}
            onStatus={setStatus}
          />
        )}
      </main>
    </section>
    );
  }
  if (view === "system-plugins") {
    return (
      <section className="system-config-page">
        <SystemConfigList
          emptyMessage={t("settings.system.emptyPlugins")}
          items={pluginsSection.items}
          pendingKey={pendingKey}
          selectedItemId={selectedItemId}
          sectionId="plugins"
          status={status}
          title={t("settings.tab.systemPlugins")}
          onSelect={onSelect}
          onToggle={onToggle}
          onDelete={onDelete}
        />
        <main className="system-config-main">
          <SystemConfigEmptyDetail message={t("settings.system.selectPluginDetail")} />
        </main>
      </section>
    );
  }
  return (
    <section className="system-config-page">
      <SystemConfigList
        emptyMessage={t("settings.system.emptyMcp")}
        items={mcpSection.items}
        pendingKey={pendingKey}
        selectedItemId={selectedItemId}
        sectionId="mcp"
        status={status}
        title={t("settings.tab.systemMcp")}
        onSelect={onSelect}
        onToggle={onToggle}
        onDelete={onDelete}
      >
        <div className="system-config-editor system-config-sidebar-form">
          <div className="system-config-editor-header">
            <span>{t("settings.system.addMcp")}</span>
            <small>{t("settings.system.addMcpHint")}</small>
          </div>
          <label className="settings-field">
            <span>MCP ID</span>
            <input value={mcpId} onChange={(event) => setMcpId(event.target.value)} placeholder="filesystem" />
          </label>
          <label className="settings-field system-config-json">
            <span>JSON</span>
            <textarea value={mcpJson} onChange={(event) => setMcpJson(event.target.value)} spellCheck={false} />
          </label>
          <label className="settings-field settings-field-checkbox">
            <span>{t("common.enabled")}</span>
            <input type="checkbox" checked={mcpEnabled} onChange={(event) => setMcpEnabled(event.target.checked)} />
          </label>
          <div className="settings-actions">
            <button
              type="button"
              className="system-config-primary-button"
              disabled={mcpId.trim() === "" || mcpMutation.isPending}
              onClick={saveMcp}
            >
              <SystemSaveIcon />
              {t("settings.system.saveMcp")}
            </button>
          </div>
        </div>
      </SystemConfigList>
      <main className="system-config-main">
        {selectedItemId === null ? (
          <SystemConfigEmptyDetail message={t("settings.system.selectMcpDetail")} />
        ) : (
          <SystemAgentConfigDetail
            sectionId="mcp"
            itemId={selectedItemId}
            onConfigChange={setConfig}
            onReset={onReset}
            onStatus={setStatus}
          />
        )}
      </main>
    </section>
  );
}

function SystemConfigEmptyDetail({ message }: { message: string }) {
  return (
    <section className="system-config-detail system-config-empty-detail">
      <p className="muted">{message}</p>
    </section>
  );
}
