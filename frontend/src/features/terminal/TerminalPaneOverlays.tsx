import { TerminalQuickInput } from "./TerminalQuickInput";
import { terminalStatusLabel, VIRTUAL_KEYS } from "./terminalPaneConstants";
import type { TerminalConnectionStatus } from "./TerminalPaneTypes";
import { useI18n } from "../../i18n";
import type { CustomQuickKey } from "../../terminalQuickKeys";

type VirtualKeysProps = {
  connectionStatus: TerminalConnectionStatus;
  onKeyInput: (data: string) => void;
  onPaste: () => void;
  onCopy: () => void;
};

export function TerminalVirtualKeys({
  connectionStatus,
  onKeyInput,
  onPaste,
  onCopy,
}: VirtualKeysProps) {
  const { t } = useI18n();

  return (
    <div className="terminal-virtual-keys" aria-label={t("terminal.virtualKeys")}>
      {VIRTUAL_KEYS.map((key) => (
        <button
          type="button"
          key={key.label}
          disabled={connectionStatus !== "connected"}
          onMouseDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
          }}
          onTouchStart={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            onKeyInput(key.value);
          }}
        >
          {key.label}
        </button>
      ))}
      <button
        type="button"
        disabled={connectionStatus !== "connected"}
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onTouchStart={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          onPaste();
        }}
      >
        {t("common.paste")}
      </button>
      <button
        type="button"
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onTouchStart={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          onCopy();
        }}
      >
        {t("common.copy")}
      </button>
    </div>
  );
}

type QuickInputOverlayProps = {
  open: boolean;
  draft: string;
  canSend: boolean;
  customQuickKeys: CustomQuickKey[];
  onDraftChange: (draft: string) => void;
  onSubmit: (draftOverride?: string) => boolean;
  onCancel: () => void;
  onCustomQuickKeySubmit?: (quickKey: CustomQuickKey) => boolean;
};

export function TerminalQuickInputOverlay({
  open,
  draft,
  canSend,
  customQuickKeys,
  onDraftChange,
  onSubmit,
  onCancel,
  onCustomQuickKeySubmit,
}: QuickInputOverlayProps) {
  if (!open) {
    return null;
  }

  return (
    <TerminalQuickInput
      value={draft}
      canSend={canSend}
      onValueChange={onDraftChange}
      onSubmit={onSubmit}
      onCancel={onCancel}
      customQuickKeys={customQuickKeys}
      onCustomQuickKeySubmit={onCustomQuickKeySubmit}
      autoFocus
    />
  );
}

export function TerminalConnectionOverlay({ status }: { status: TerminalConnectionStatus }) {
  const { t } = useI18n();

  if (status === "connected") {
    return null;
  }
  return (
    <div className={`terminal-connection-status ${status}`} role="status">
      {terminalStatusLabel(status, t)}
    </div>
  );
}
