import { useCallback, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import {
  effectiveKeyboardShortcut,
  KEYBOARD_SHORTCUT_DEFINITIONS,
  shortcutForCapture,
  type KeyboardShortcut,
  type KeyboardShortcutId
} from "../../keyboardShortcuts";
import { useI18n } from "../../i18n";
import type { CustomQuickKey } from "../../terminalQuickKeys";
import type { SettingsDraft, ShortcutBindingTarget } from "./settingsModalData";

type ShortcutRow = {
  target: ShortcutBindingTarget;
  label: string;
  shortcut: KeyboardShortcut | null;
  defaultShortcut?: KeyboardShortcut;
};

type UseShortcutBindingsArgs = {
  changeDraft: (patch: Partial<SettingsDraft>) => void;
  customQuickKeys: CustomQuickKey[];
  keyboardShortcutBindings: SettingsDraft["keyboardShortcutBindings"];
  updateQuickKey: (id: string, patch: Partial<CustomQuickKey>) => void;
  updateQuickKeyDraft: (patch: Partial<CustomQuickKey>) => void;
};

export function useShortcutBindings({
  changeDraft,
  customQuickKeys,
  keyboardShortcutBindings,
  updateQuickKey,
  updateQuickKeyDraft
}: UseShortcutBindingsArgs) {
  const { t } = useI18n();
  const [recordingShortcutTarget, setRecordingShortcutTarget] = useState<ShortcutBindingTarget | null>(null);
  const shortcutRows: ShortcutRow[] = useMemo(() => [
    ...KEYBOARD_SHORTCUT_DEFINITIONS.map((definition) => ({
      target: { type: "builtin", id: definition.id } as ShortcutBindingTarget,
      label: t(definition.labelKey),
      shortcut: effectiveKeyboardShortcut(definition.id, keyboardShortcutBindings),
      defaultShortcut: definition.defaultShortcut
    })),
    ...customQuickKeys.map((quickKey) => ({
      target: { type: "quick-key", id: quickKey.id } as ShortcutBindingTarget,
      label: t("shortcut.quickKeyPrefix", { label: quickKey.label }),
      shortcut: quickKey.shortcut ?? null
    }))
  ], [customQuickKeys, keyboardShortcutBindings, t]);

  const bindShortcut = useCallback((target: ShortcutBindingTarget, shortcut: KeyboardShortcut | null) => {
    if (target.type === "builtin") {
      changeDraft({
        keyboardShortcutBindings: {
          ...keyboardShortcutBindings,
          [target.id]: shortcut
        }
      });
      return;
    }

    if (target.type === "quick-key-draft") {
      updateQuickKeyDraft({ shortcut });
      return;
    }

    updateQuickKey(target.id, { shortcut });
  }, [changeDraft, keyboardShortcutBindings, updateQuickKey, updateQuickKeyDraft]);

  const bindDefaultShortcut = useCallback((id: KeyboardShortcutId) => {
    const nextBindings = { ...keyboardShortcutBindings };
    delete nextBindings[id];
    changeDraft({ keyboardShortcutBindings: nextBindings });
  }, [changeDraft, keyboardShortcutBindings]);

  const resetAllBuiltInShortcuts = useCallback(() => {
    changeDraft({ keyboardShortcutBindings: {} });
  }, [changeDraft]);

  const captureShortcut = useCallback((target: ShortcutBindingTarget, event: ReactKeyboardEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();

    if (event.key === "Escape") {
      setRecordingShortcutTarget(null);
      return;
    }

    const shortcut = shortcutForCapture(event.nativeEvent);
    if (shortcut === null) {
      return;
    }

    bindShortcut(target, shortcut);
    setRecordingShortcutTarget(null);
  }, [bindShortcut]);

  return {
    bindDefaultShortcut,
    bindShortcut,
    captureShortcut,
    recordingShortcutTarget,
    resetAllBuiltInShortcuts,
    setRecordingShortcutTarget,
    shortcutRows
  };
}
