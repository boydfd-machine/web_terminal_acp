import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { keyboardShortcutLabel, type KeyboardShortcut } from "../keyboardShortcuts";
import { useI18n } from "../i18n";
import { shortcutTargetKey, type ShortcutBindingTarget } from "./settingsModalData";

export function ShortcutRecorder({
  label,
  shortcut,
  target,
  recordingTarget,
  conflictLabel,
  onStartRecording,
  onCapture,
  onClear
}: {
  label: string;
  shortcut: KeyboardShortcut | null;
  target: ShortcutBindingTarget;
  recordingTarget: ShortcutBindingTarget | null;
  conflictLabel: string | null;
  onStartRecording: (target: ShortcutBindingTarget) => void;
  onCapture: (target: ShortcutBindingTarget, event: ReactKeyboardEvent<HTMLButtonElement>) => void;
  onClear: (target: ShortcutBindingTarget) => void;
}) {
  const { t } = useI18n();
  const recording = recordingTarget !== null && shortcutTargetKey(recordingTarget) === shortcutTargetKey(target);

  return (
    <div className="shortcut-recorder">
      <button
        type="button"
        className={recording ? "shortcut-recorder-button recording" : "shortcut-recorder-button"}
        aria-label={t("shortcut.bind", { label })}
        onClick={() => {
          if (recording) {
            return;
          }
          onStartRecording(target);
        }}
        onKeyDown={(event) => {
          if (recording) {
            onCapture(target, event);
          }
        }}
      >
        {recording ? t("shortcut.recording") : keyboardShortcutLabel(shortcut, t)}
      </button>
      <button type="button" onClick={() => onClear(target)}>
        {t("shortcut.clear")}
      </button>
      {conflictLabel !== null && (
        <span className="shortcut-conflict">{t("shortcut.conflict", { label: conflictLabel })}</span>
      )}
    </div>
  );
}
