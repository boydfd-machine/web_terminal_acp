import { useI18n } from "../i18n";
import type { AgentConfig, AgentConfigSelection } from "../types";
import { AgentConfigPicker } from "./AgentConfigPicker";

type TerminalCreateConfigAccordionProps = {
  config: AgentConfig | null;
  configSummary: string;
  expanded: boolean;
  isError: boolean;
  isFetching: boolean;
  isLoading: boolean;
  panelId: string;
  selection: AgentConfigSelection | null;
  onSelectionChange: (selection: AgentConfigSelection) => void;
  onToggle: () => void;
};

export function TerminalCreateConfigAccordion({
  config,
  configSummary,
  expanded,
  isError,
  isFetching,
  isLoading,
  panelId,
  selection,
  onSelectionChange,
  onToggle
}: TerminalCreateConfigAccordionProps) {
  const { t } = useI18n();

  return (
    <>
      <button
        type="button"
        className="settings-nav-row terminal-create-config-row"
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span>{t("terminal.create.config")}</span>
        <strong>{configSummary}</strong>
      </button>
      {expanded && (
        <div id={panelId} className="terminal-create-config-panel">
          <AgentConfigPicker
            config={config}
            selection={selection}
            isLoading={isLoading}
            isError={isError}
            isFetching={isFetching}
            onSelectionChange={onSelectionChange}
          />
        </div>
      )}
    </>
  );
}
