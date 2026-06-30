import { describe, expect, it } from "vitest";

import {
  ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
  ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
  normalizeArtifactProjectTodoCreateMessage
} from "../src/artifactProjectTodoBridge";

describe("artifact project todo bridge", () => {
  it("normalizes project todo card create messages", () => {
    const message = normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      request_id: "request-1",
      card: {
        title: "  Follow up from artifact  ",
        description: "  Add the missing board state  ",
        status: "BLOCKED",
        todo_type_id: "research.card",
        artifact_kinds: ["agent_trace_graph", "project:user_journey"],
        input_artifact_ids: [" artifact-current ", "artifact-flow"],
        execution_kind: "PERIODIC",
        terminal_policy: "REUSE_LATEST",
        trigger_strategy: "CRON",
        cron_expression: "0 9 * * 1",
        schedule_enabled: true,
        review_strategy: "GITHUB",
        review_agent: "codex",
        review_agent_profile_id: "profile-1",
        artifact_model_selection: {
          preset_id: "openai-artifacts",
          model: "gpt-5-codex",
          codex_model_reasoning_effort: "high"
        }
      }
    });

    expect(message).toEqual({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      request_id: "request-1",
      card: {
        title: "Follow up from artifact",
        description: "Add the missing board state",
        status: "BLOCKED",
        todo_type_id: "research.card",
        artifact_kinds: ["agent_trace_graph", "project:user_journey"],
        input_artifact_ids: ["artifact-current", "artifact-flow"],
        execution_kind: "PERIODIC",
        terminal_policy: "REUSE_LATEST",
        trigger_strategy: "CRON",
        cron_expression: "0 9 * * 1",
        schedule_enabled: true,
        review_strategy: "GITHUB",
        review_agent: "codex",
        review_agent_profile_id: "profile-1",
        artifact_model_selection: {
          preset_id: "openai-artifacts",
          model: "gpt-5-codex",
          codex_model_reasoning_effort: "high"
        }
      }
    });
  });

  it("accepts long project todo descriptions from artifact cards", () => {
    const description = "测".repeat(100_000);

    const message = normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: {
        title: "Summarize long source",
        description
      }
    });

    expect(message?.card.description).toBe(description);
  });

  it("rejects malformed or over-broad card payloads", () => {
    expect(normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: { title: "" }
    })).toBeNull();
    expect(normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: { title: "Valid", status: "DONE" }
    })).toBeNull();
    expect(normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: { title: "Valid", todo_type_id: "bad id" }
    })).toBeNull();
    expect(normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: { title: "Valid", artifact_kinds: Array.from({ length: 21 }, (_, index) => `kind-${index}`) }
    })).toBeNull();
    expect(normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: { title: "Valid", input_artifact_ids: Array.from({ length: 51 }, (_, index) => `artifact-${index}`) }
    })).toBeNull();
    expect(normalizeArtifactProjectTodoCreateMessage({
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      card: { title: "Valid", artifact_model_selection: { model: "missing-preset" } }
    })).toBeNull();
  });
});
