import { useCallback, useState } from "react";

import { createCustomQuickKey, quickKeyToken, type CustomQuickKey } from "../../terminalQuickKeys";
import type { SettingsDraft } from "./settingsModalData";

type UseQuickKeysSettingsArgs = {
  changeDraft: (patch: Partial<SettingsDraft>) => void;
  customQuickKeys: CustomQuickKey[];
};

export function useQuickKeysSettings({ changeDraft, customQuickKeys }: UseQuickKeysSettingsArgs) {
  const [quickKeyDraft, setQuickKeyDraft] = useState<CustomQuickKey>(() => createCustomQuickKey());
  const quickKeyDraftValid = quickKeyDraft.label.trim().length > 0 && quickKeyDraft.input.length > 0;

  const updateQuickKeyDraft = useCallback((patch: Partial<CustomQuickKey>) => {
    setQuickKeyDraft((current) => ({ ...current, ...patch }));
  }, []);

  const resetQuickKeyDraft = useCallback(() => {
    setQuickKeyDraft(createCustomQuickKey());
  }, []);

  const addQuickKey = useCallback(() => {
    if (!quickKeyDraftValid) {
      return;
    }

    changeDraft({
      customQuickKeys: [
        ...customQuickKeys,
        {
          ...quickKeyDraft,
          label: quickKeyDraft.label.trim()
        }
      ]
    });
    resetQuickKeyDraft();
  }, [changeDraft, customQuickKeys, quickKeyDraft, quickKeyDraftValid, resetQuickKeyDraft]);

  const updateQuickKey = useCallback((id: string, patch: Partial<CustomQuickKey>) => {
    changeDraft({
      customQuickKeys: customQuickKeys.map((quickKey) => (
        quickKey.id === id ? { ...quickKey, ...patch } : quickKey
      ))
    });
  }, [changeDraft, customQuickKeys]);

  const removeQuickKey = useCallback((id: string) => {
    changeDraft({
      customQuickKeys: customQuickKeys.filter((quickKey) => quickKey.id !== id)
    });
  }, [changeDraft, customQuickKeys]);

  const appendSpecialKeyToDraft = useCallback((token: string) => {
    updateQuickKeyDraft({ input: `${quickKeyDraft.input}${quickKeyToken(token)}` });
  }, [quickKeyDraft.input, updateQuickKeyDraft]);

  return {
    addQuickKey,
    appendSpecialKeyToDraft,
    quickKeyDraft,
    quickKeyDraftValid,
    removeQuickKey,
    resetQuickKeyDraft,
    updateQuickKey,
    updateQuickKeyDraft
  };
}
