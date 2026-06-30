import { beforeEach, describe, expect, it } from "vitest";

import {
  DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS,
  MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS,
  clampArtifactTerminalRetentionSeconds,
  clearRuntimeAppPreferencesForTests,
  readAgentModelSelectionSettings,
  readArtifactModelSelectionSettings,
  readArtifactTerminalRetentionSeconds,
  readTerminalTimeRange,
  readThemeSkin,
  writeAgentModelSelectionSettings,
  writeArtifactModelSelectionSettings,
  writeArtifactTerminalRetentionSeconds,
  writeTerminalTimeRange,
  writeThemeSkin
} from "../src/userPreferences";

beforeEach(() => {
  clearRuntimeAppPreferencesForTests();
  window.localStorage.clear();
});

describe("userPreferences terminal time range", () => {
  it("defaults terminal lists to 7 days", () => {
    expect(readTerminalTimeRange()).toBe("7d");
  });

  it("persists a supported terminal time range", () => {
    writeTerminalTimeRange("14d");

    expect(readTerminalTimeRange()).toBe("14d");
  });

  it("ignores unsupported stored terminal time ranges", () => {
    window.localStorage.setItem("web-terminal-acp:terminal-time-range", "2d");

    expect(readTerminalTimeRange()).toBe("7d");
  });
});

describe("userPreferences theme skin", () => {
  it("defaults to the existing application skin", () => {
    expect(readThemeSkin()).toBe("default");
  });

  it("persists a supported theme skin", () => {
    writeThemeSkin("raycast");

    expect(readThemeSkin()).toBe("raycast");
  });

  it("ignores unsupported stored theme skins", () => {
    window.localStorage.setItem("web-terminal-acp:theme-skin", "unsupported");

    expect(readThemeSkin()).toBe("default");
  });
});

describe("userPreferences artifact terminal retention", () => {
  it("defaults artifact terminals to a ten minute retention", () => {
    expect(readArtifactTerminalRetentionSeconds()).toBe(DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS);
  });

  it("persists artifact terminal retention seconds", () => {
    writeArtifactTerminalRetentionSeconds(120);

    expect(readArtifactTerminalRetentionSeconds()).toBe(120);
  });

  it("clamps invalid artifact terminal retention values", () => {
    expect(clampArtifactTerminalRetentionSeconds(Number.NaN)).toBe(DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS);
    expect(clampArtifactTerminalRetentionSeconds(-1)).toBe(0);
    expect(clampArtifactTerminalRetentionSeconds(90.4)).toBe(90);
    expect(clampArtifactTerminalRetentionSeconds(MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS + 1))
      .toBe(MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS);
  });
});

describe("userPreferences agent model selections", () => {
  it("persists per-agent default model selections", () => {
    writeAgentModelSelectionSettings({
      codex: { preset_id: "openai-main", model: "model-b" },
      claude: {
        preset_id: "anthropic-main",
        claude: { mode: "split", opus_model: "opus", sonnet_model: "sonnet", haiku_model: "haiku" }
      }
    });

    expect(readAgentModelSelectionSettings()).toEqual({
      codex: { preset_id: "openai-main", model: "model-b" },
      claude: {
        preset_id: "anthropic-main",
        claude: { mode: "split", opus_model: "opus", sonnet_model: "sonnet", haiku_model: "haiku" }
      }
    });
  });

  it("ignores malformed stored agent model selections", () => {
    window.localStorage.setItem("web-terminal-acp:agent-model-selections", JSON.stringify({
      codex: { model: "missing-preset" },
      claude: { preset_id: "anthropic-main" },
      cursor: null
    }));

    expect(readAgentModelSelectionSettings()).toEqual({
      claude: { preset_id: "anthropic-main" },
      cursor: null
    });
  });
});

describe("userPreferences artifact model selections", () => {
  it("persists per-agent artifact default model selections", () => {
    writeArtifactModelSelectionSettings({
      codex: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high",
        codex_plan_mode_reasoning_effort: "medium"
      },
      claude: {
        preset_id: "anthropic-artifacts",
        claude: { mode: "all", model: "claude-sonnet-4.5" },
        claude_reasoning_effort: "max"
      }
    });

    expect(readArtifactModelSelectionSettings()).toEqual({
      codex: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high",
        codex_plan_mode_reasoning_effort: "medium"
      },
      claude: {
        preset_id: "anthropic-artifacts",
        claude: { mode: "all", model: "claude-sonnet-4.5" },
        claude_reasoning_effort: "max"
      }
    });
  });

  it("ignores malformed stored artifact model selections", () => {
    window.localStorage.setItem("web-terminal-acp:artifact-model-selections", JSON.stringify({
      codex: { model: "missing-preset" },
      claude: { preset_id: "anthropic-artifacts" },
      cursor: null
    }));

    expect(readArtifactModelSelectionSettings()).toEqual({
      claude: { preset_id: "anthropic-artifacts" },
      cursor: null
    });
  });
});
