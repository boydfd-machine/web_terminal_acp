import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { DEFAULT_AGENT_CLIENTS, agentLaunchForClient, agentLaunchForKind } from "../src/agentLaunch";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("agent launch defaults", () => {
  it("includes saved default model selections in direct launch payloads", () => {
    window.localStorage.setItem("web-terminal-acp:agent-model-selections", JSON.stringify({
      claude: {
        preset_id: "anthropic-main",
        claude: { mode: "all", model: "claude-sonnet" }
      }
    }));

    expect(agentLaunchForKind("claude")).toMatchObject({
      agent: "claude",
      command: "claude",
      config: null,
      model_selection: {
        preset_id: "anthropic-main",
        claude: { mode: "all", model: "claude-sonnet" }
      }
    });
    expect(agentLaunchForClient("claude", DEFAULT_AGENT_CLIENTS)).toMatchObject({
      agent: "claude",
      command: "claude",
      config: null,
      model_selection: {
        preset_id: "anthropic-main",
        claude: { mode: "all", model: "claude-sonnet" }
      }
    });
  });
});
