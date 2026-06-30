import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchCursorOfficialModels } from "../apiAgents";
import {
  cursorOfficialModelSelection,
  cursorOfficialModelValue,
  isCursorOfficialModelSelection
} from "../cursorOfficialModels";
import { useI18n } from "../i18n";
import type { AgentModelSelection } from "../types";

export function CursorOfficialModelPicker({
  clientId,
  value,
  onChange
}: {
  clientId: string | null;
  value: AgentModelSelection | null;
  onChange: (value: AgentModelSelection | null) => void;
}) {
  const { t } = useI18n();
  const modelsQuery = useQuery({
    queryKey: ["cursor-official-models", clientId],
    queryFn: () => fetchCursorOfficialModels(clientId as string),
    enabled: clientId !== null,
    staleTime: 60_000
  });
  const models = modelsQuery.data?.models ?? [];
  const selectedModel = cursorOfficialModelValue(value);

  useEffect(() => {
    if (value === null || !isCursorOfficialModelSelection(value) || modelsQuery.isLoading) {
      return;
    }
    if (selectedModel && !models.some((model) => model.id === selectedModel)) {
      onChange(null);
    }
  }, [models, modelsQuery.isLoading, onChange, selectedModel, value]);

  return (
    <section className="agent-model-picker">
      <label className="settings-field">
        <span>{t("terminal.model.name")}</span>
        <select
          value={selectedModel}
          onChange={(event) => {
            const nextModel = event.target.value;
            onChange(nextModel ? cursorOfficialModelSelection(nextModel) : null);
          }}
          disabled={modelsQuery.isLoading || clientId === null}
        >
          <option value="">{t("terminal.model.clientDefault")}</option>
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.label}
            </option>
          ))}
        </select>
      </label>
      {modelsQuery.isError && <p className="error settings-hint">{t("terminal.model.loadFailed")}</p>}
    </section>
  );
}
