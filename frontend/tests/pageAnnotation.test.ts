import { describe, expect, it } from "vitest";

import {
  buildPageAnnotationTodoInput,
  normalizePageAnnotationSelection,
} from "../src/pageAnnotation";
import type { PageAnnotationEvidence } from "../src/pageAnnotationEvidence";

const baseEvidence: PageAnnotationEvidence = {
  route: "/clients/client-1/terminals/window-1?debug=true#pane",
  viewport: { width: 1024, height: 768, devicePixelRatio: 2 },
  selection: { left: 12, top: 24, width: 180, height: 96 },
  appState: {
    clientId: "client-1",
    projectPath: "/workspace",
    windowId: "window-1",
    workspaceMode: "terminal",
    themeSkin: "default"
  },
  primaryTarget: {
    selector: '[data-debug-id="project-todo-card"]',
    selectorConfidence: "high",
    tagName: "article",
    role: null,
    accessibleName: null,
    text: "Fix board drag",
    classNames: ["project-todo-card", "selected"],
    safeAttributes: { "data-debug-id": "project-todo-card", "data-project-todo-id": "todo-1" },
    rect: { left: 10, top: 20, width: 190, height: 100 },
    style: {
      display: "grid",
      position: "relative",
      "font-size": "13px"
    },
    ancestry: [
      'main[data-debug-id="app-shell"]',
      'section[data-debug-id="workspace"]',
      'article[data-debug-id="project-todo-card"]'
    ]
  },
  elements: []
};

describe("page annotation todo formatting", () => {
  it("normalizes drag selections and drops tiny selections", () => {
    expect(normalizePageAnnotationSelection({ x: 30, y: 50 }, { x: 10, y: 20 })).toEqual({
      left: 10,
      top: 20,
      width: 20,
      height: 30
    });
    expect(normalizePageAnnotationSelection({ x: 10, y: 10 }, { x: 15, y: 20 })).toBeNull();
  });

  it("builds a todo title and evidence-rich description", () => {
    const input = buildPageAnnotationTodoInput({
      userCommand: "Investigate whether this card metadata is easy to scan.\nDo not change code yet.",
      evidence: baseEvidence
    });

    expect(input.title).toBe("Annotation: Investigate whether this card metadata is easy to scan.");
    expect(input.description).toContain("Source: Debug page annotation");
    expect(input.description).toContain("Route: /clients/client-1/terminals/window-1?debug=true#pane");
    expect(input.description).toContain("Workspace mode: terminal");
    expect(input.description).toContain("Selection: x=12, y=24, width=180, height=96");
    expect(input.description).toContain('selector: [data-debug-id="project-todo-card"]');
    expect(input.description).toContain("selector confidence: high");
    expect(input.description).toContain("display: grid");
    expect(input.description).toContain(
      "Follow the user's command:\nInvestigate whether this card metadata is easy to scan."
    );
    expect(input.description).not.toContain("Requested change:");
    expect(input.description).not.toContain("Acceptance criteria:");
  });

  it("falls back to route when the request is blank", () => {
    const input = buildPageAnnotationTodoInput({
      userCommand: "   ",
      evidence: {
        ...baseEvidence,
        route: "/projects",
        appState: { ...baseEvidence.appState, workspaceMode: "kanban" }
      }
    });

    expect(input.title).toBe("Annotation: /projects");
    expect(input.description).toContain("Follow the user's command:\nNo user command provided.");
  });
});
