import { describe, expect, it } from "vitest";

import {
  agentModelSelectionSettingsEqual,
  createSettingsDraft,
  settingsDraftsEqual
} from "../src/features/settings/settingsModalData";

function baseDraft() {
  return createSettingsDraft({
    appLocale: "zh-CN",
    apiBase: "",
    summaryOutputLanguage: "中文",
    terminalGroupingMode: "project-topic",
    artifactTerminalRetentionSeconds: 600,
    themeSkin: "default",
    desktopNotificationsEnabled: true,
    agentCommandSettings: {},
    agentModelSelectionSettings: {},
    artifactModelSelectionSettings: {},
    keyboardShortcutBindings: {},
    customQuickKeys: []
  });
}

describe("settings modal data model selections", () => {
  it("treats reasoning effort overrides as model selection changes", () => {
    expect(agentModelSelectionSettingsEqual(
      { codex: { preset_id: "openai", model: "gpt-5-codex", codex_model_reasoning_effort: "low" } },
      { codex: { preset_id: "openai", model: "gpt-5-codex", codex_model_reasoning_effort: "high" } }
    )).toBe(false);
  });

  it("tracks artifact default model selections separately from terminal defaults", () => {
    const saved = baseDraft();
    const draft = createSettingsDraft({
      ...saved,
      artifactModelSelectionSettings: {
        codex: {
          preset_id: "openai-artifacts",
          model: "gpt-5-codex",
          codex_plan_mode_reasoning_effort: "xhigh"
        }
      }
    });

    expect(settingsDraftsEqual(draft, saved)).toBe(false);
  });
});
