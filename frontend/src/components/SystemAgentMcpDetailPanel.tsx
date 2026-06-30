import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchSystemMcpDetail } from "../api";
import { useI18n } from "../i18n";
import type { SystemMcpDetail, SystemMcpTool } from "../types";
import { mcpToolParameters } from "./systemAgentConfigDetailModel";
import { SystemDetailHeader } from "./SystemAgentConfigDetailHeader";

type SystemMcpViewMode = "visual" | "json";
type SystemConfigSectionId = "skills" | "mcp";

function json(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function SystemMcpDetailPanel({
  itemId,
  onReset
}: {
  itemId: string;
  onReset: (sectionId: SystemConfigSectionId, itemId: string) => void;
}) {
  const { t } = useI18n();
  const [viewMode, setViewMode] = useState<SystemMcpViewMode>("visual");
  const [selectedToolName, setSelectedToolName] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["system-mcp-detail", itemId],
    queryFn: () => fetchSystemMcpDetail(itemId)
  });
  const detail = query.data ?? null;

  useEffect(() => {
    setViewMode("visual");
    setSelectedToolName(null);
  }, [itemId]);

  useEffect(() => {
    if (detail === null) {
      return;
    }
    setSelectedToolName((current) => (
      current !== null && detail.tools.some((tool) => tool.name === current)
        ? current
        : detail.tools[0]?.name ?? null
    ));
  }, [detail]);

  if (query.isLoading) {
    return <section className="system-config-detail"><p className="muted">{t("settings.system.loadingDetail")}</p></section>;
  }
  if (query.isError || detail === null) {
    return <section className="system-config-detail"><p className="error">{t("settings.system.loadDetailFailed")}</p></section>;
  }

  return (
    <section className="system-config-detail" aria-label={t("settings.system.detailLabel", { name: detail.name })}>
      <SystemDetailHeader detail={detail} onReset={() => onReset("mcp", itemId)} />
      <div className="system-config-detail-toolbar">
        <div className="workspace-mode-toggle" role="group" aria-label={t("settings.system.mcpDisplayMode")}>
          <button type="button" className={viewMode === "visual" ? "active" : ""} aria-pressed={viewMode === "visual"} onClick={() => setViewMode("visual")}>
            {t("settings.system.visualDisplay")}
          </button>
          <button type="button" className={viewMode === "json" ? "active" : ""} aria-pressed={viewMode === "json"} onClick={() => setViewMode("json")}>
            JSON
          </button>
        </div>
      </div>
      {viewMode === "visual" ? (
        <SystemMcpVisualDetail detail={detail} selectedToolName={selectedToolName} onSelectTool={setSelectedToolName} />
      ) : (
        <SystemMcpJsonDetail detail={detail} />
      )}
    </section>
  );
}

function SystemMcpVisualDetail({
  detail,
  selectedToolName,
  onSelectTool
}: {
  detail: SystemMcpDetail;
  selectedToolName: string | null;
  onSelectTool: (toolName: string) => void;
}) {
  const { t } = useI18n();
  const selectedTool = detail.tools.find((tool) => tool.name === selectedToolName) ?? detail.tools[0] ?? null;
  return (
    <div className="system-config-mcp-visual">
      <section className="system-config-mcp-server-summary">
        <div className="system-config-detail-section-title"><h4>{t("settings.system.server")}</h4></div>
        <div className="system-config-mcp-summary-grid">
          <SystemMcpSummaryField label={t("settings.system.type")} value={detail.server.type} />
          <SystemMcpSummaryField label={t("settings.system.command")} value={detail.server.command} />
          <SystemMcpSummaryField label="URL" value={detail.server.url ?? detail.server.server_url} />
          <SystemMcpSummaryField label={t("settings.system.transport")} value={detail.server.transport} />
        </div>
      </section>
      <section className="system-config-mcp-tools">
        <div className="system-config-detail-section-title"><h4>{t("settings.system.tools")}</h4><span>{detail.tools.length}</span></div>
        {detail.tools.length === 0 ? (
          <p className="muted system-config-detail-empty">{t("settings.system.noDeclaredTools")}</p>
        ) : (
          <div className="system-config-mcp-tool-browser">
            <div className="system-config-mcp-tool-list" role="list" aria-label={t("settings.system.tools")}>
              {detail.tools.map((tool) => (
                <button key={tool.name} type="button" className={selectedTool?.name === tool.name ? "selected" : ""} aria-pressed={selectedTool?.name === tool.name} onClick={() => onSelectTool(tool.name)}>
                  <strong>{tool.name}</strong>
                  <span>{tool.description?.trim() || t("settings.system.noDescription")}</span>
                </button>
              ))}
            </div>
            {selectedTool !== null && <SystemMcpToolItem tool={selectedTool} />}
          </div>
        )}
      </section>
    </div>
  );
}

function SystemMcpSummaryField({ label, value }: { label: string; value: unknown }) {
  const displayValue = typeof value === "string" && value.trim() !== "" ? value : "-";
  return <div><span>{label}</span><strong>{displayValue}</strong></div>;
}

function SystemMcpJsonDetail({ detail }: { detail: SystemMcpDetail }) {
  const { t } = useI18n();
  return (
    <div className="system-config-mcp-detail-grid">
      <div className="system-config-json-preview"><h4>{t("settings.system.serverJson")}</h4><pre>{json(detail.server)}</pre></div>
      <div className="system-config-json-preview"><h4>{t("settings.system.toolsJson")}</h4><pre>{json(detail.tools)}</pre></div>
    </div>
  );
}

function SystemMcpToolItem({ tool }: { tool: SystemMcpTool }) {
  const { t } = useI18n();
  const parameters = mcpToolParameters(tool.input_schema);
  return (
    <li className="system-config-mcp-tool">
      <div className="system-config-mcp-tool-header"><span>{t("settings.system.toolName")}</span><strong>{tool.name}</strong></div>
      <div className="system-config-mcp-tool-description"><span>{t("settings.system.toolDescription")}</span><p>{tool.description?.trim() || t("settings.system.noDescription")}</p></div>
      <div className="system-config-mcp-parameters">
        <span>{t("settings.system.parameters")}</span>
        {parameters.length === 0 ? (
          Object.keys(tool.input_schema).length === 0 ? <p className="muted">{t("settings.system.noParameters")}</p> : <pre>{json(tool.input_schema)}</pre>
        ) : (
          <div className="system-config-mcp-parameter-list" role="list">
            {parameters.map((parameter) => (
              <div key={parameter.name} className="system-config-mcp-parameter" role="listitem">
                <div><strong>{parameter.name}</strong><small>{parameter.required ? t("settings.system.required") : t("common.optional")}</small></div>
                <code>{parameter.type}</code>
                {parameter.description !== null && <p>{parameter.description}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}
