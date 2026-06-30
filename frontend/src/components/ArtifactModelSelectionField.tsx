import { useEffect } from "react";

import { artifactModelAgentSupportsSelection } from "../artifactModelSelection";
import { useI18n } from "../i18n";
import type { AgentLaunchKind, AgentModelSelection } from "../types";
import { AgentModelSelectionPicker } from "./AgentModelSelectionPicker";

export function ArtifactModelSelectionField({
  agent,
  className,
  value,
  onChange
}: {
  agent: AgentLaunchKind | null;
  className?: string;
  value: AgentModelSelection | null;
  onChange: (value: AgentModelSelection | null) => void;
}) {
  const { t } = useI18n();
  const supported = artifactModelAgentSupportsSelection(agent);

  useEffect(() => {
    if (!supported && value !== null) {
      onChange(null);
    }
  }, [onChange, supported, value]);

  if (!supported) {
    return null;
  }

  return (
    <fieldset className={["artifact-model-selection-field", className].filter(Boolean).join(" ")}>
      <legend>{t("artifact.model.label")}</legend>
      <AgentModelSelectionPicker agent={agent} value={value} onChange={onChange} />
    </fieldset>
  );
}
