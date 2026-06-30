import { afterEach, describe, expect, it, vi } from "vitest";

import {
  collectPageAnnotationEvidence,
  pageAnnotationRectIntersects,
} from "../src/pageAnnotationEvidence";

afterEach(() => {
  document.body.replaceChildren();
  delete (document as Partial<Document>).elementsFromPoint;
  vi.restoreAllMocks();
});

function mockRect(element: Element, rect: Partial<DOMRect>): void {
  const fullRect = {
    left: rect.left ?? 0,
    top: rect.top ?? 0,
    width: rect.width ?? 0,
    height: rect.height ?? 0,
    right: (rect.left ?? 0) + (rect.width ?? 0),
    bottom: (rect.top ?? 0) + (rect.height ?? 0),
    x: rect.left ?? 0,
    y: rect.top ?? 0,
    toJSON: () => ({})
  } as DOMRect;
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue(fullRect);
}

describe("page annotation evidence", () => {
  it("detects rectangle intersections", () => {
    expect(pageAnnotationRectIntersects(
      { left: 10, top: 10, width: 20, height: 20 },
      { left: 20, top: 20, width: 20, height: 20 }
    )).toBe(true);
    expect(pageAnnotationRectIntersects(
      { left: 10, top: 10, width: 10, height: 10 },
      { left: 30, top: 30, width: 10, height: 10 }
    )).toBe(false);
  });

  it("collects a stable primary target and safe attributes", () => {
    document.body.innerHTML = `
      <main data-debug-id="app-shell">
        <section class="workspace" data-onboarding-id="workspace-root">
          <button
            class="primary action"
            data-debug-id="save-button"
            data-secret-token="do-not-copy"
            aria-label="Save project"
            title="Save"
            value="hidden-value"
          >Save now</button>
        </section>
      </main>
    `;
    const main = document.querySelector("main") as HTMLElement;
    const workspace = document.querySelector("section") as HTMLElement;
    const button = document.querySelector("button") as HTMLButtonElement;
    mockRect(main, { left: 0, top: 0, width: 500, height: 500 });
    mockRect(workspace, { left: 20, top: 20, width: 300, height: 300 });
    mockRect(button, { left: 50, top: 60, width: 120, height: 40 });

    const evidence = collectPageAnnotationEvidence({
      selection: { left: 40, top: 50, width: 160, height: 80 },
      appState: {
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "terminal",
        themeSkin: "default"
      }
    });

    expect(evidence.elements.length).toBeGreaterThan(0);
    expect(evidence.primaryTarget?.selector).toBe('[data-debug-id="save-button"]');
    expect(evidence.primaryTarget?.selectorConfidence).toBe("high");
    expect(evidence.primaryTarget?.tagName).toBe("button");
    expect(evidence.primaryTarget?.accessibleName).toBe("Save project");
    expect(evidence.primaryTarget?.safeAttributes).toEqual({
      "aria-label": "Save project",
      "data-debug-id": "save-button",
      title: "Save"
    });
    expect(evidence.primaryTarget?.text).toBe("Save now");
    expect(evidence.primaryTarget?.ancestry).toContain('main[data-debug-id="app-shell"]');
    expect(evidence.primaryTarget?.safeAttributes).not.toHaveProperty("data-secret-token");
    expect(evidence.primaryTarget?.safeAttributes).not.toHaveProperty("value");
  });

  it("sanitizes href query strings and keeps style summaries small", () => {
    document.body.innerHTML = `
      <a class="nav-link" aria-label="Open details" href="/clients/client-1?token=secret#pane">Open details</a>
    `;
    const anchor = document.querySelector("a") as HTMLAnchorElement;
    mockRect(anchor, { left: 10, top: 12, width: 100, height: 32 });
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      display: "flex",
      position: "relative",
      zIndex: "10",
      color: "rgb(1, 2, 3)",
      backgroundColor: "rgb(4, 5, 6)",
      width: "100px",
      height: "32px",
      marginTop: "1px",
      marginRight: "2px",
      marginBottom: "3px",
      marginLeft: "4px",
      paddingTop: "5px",
      paddingRight: "6px",
      paddingBottom: "7px",
      paddingLeft: "8px",
      borderRadius: "4px",
      borderTopWidth: "1px",
      borderRightWidth: "1px",
      borderBottomWidth: "1px",
      borderLeftWidth: "1px",
      borderTopStyle: "solid",
      borderRightStyle: "solid",
      borderBottomStyle: "solid",
      borderLeftStyle: "solid",
      borderTopColor: "rgb(7, 8, 9)",
      borderRightColor: "rgb(7, 8, 9)",
      borderBottomColor: "rgb(7, 8, 9)",
      borderLeftColor: "rgb(7, 8, 9)",
      boxShadow: "none",
      fontSize: "14px",
      fontWeight: "600",
      lineHeight: "20px",
      overflow: "hidden",
      gap: "8px",
      gridTemplateColumns: "none",
      flexDirection: "row",
      opacity: "1"
    } as CSSStyleDeclaration);

    const evidence = collectPageAnnotationEvidence({
      selection: { left: 0, top: 0, width: 140, height: 80 },
      appState: {
        clientId: null,
        projectPath: null,
        windowId: null,
        workspaceMode: "kanban"
      }
    });

    expect(evidence.elements.length).toBeGreaterThan(0);
    expect(evidence.primaryTarget?.safeAttributes.href).toBe("/clients/client-1#pane");
    expect(Object.keys(evidence.primaryTarget?.style ?? {})).not.toContain("cssText");
    expect(evidence.primaryTarget?.style.display).toBe("flex");
    expect(evidence.primaryTarget?.style["font-size"]).toBe("14px");
  });

  it("prefers visible modal evidence over elements covered behind it", () => {
    document.body.innerHTML = `
      <main data-debug-id="app-shell">
        <button data-debug-id="behind-action" aria-label="Delete project">Delete project</button>
      </main>
      <div class="settings-modal-backdrop"></div>
      <section class="settings-modal" role="dialog" aria-label="Settings">
        <div class="settings-modal-body"></div>
      </section>
    `;
    const main = document.querySelector("main") as HTMLElement;
    const behindButton = document.querySelector("[data-debug-id='behind-action']") as HTMLButtonElement;
    const backdrop = document.querySelector(".settings-modal-backdrop") as HTMLElement;
    const modal = document.querySelector(".settings-modal") as HTMLElement;
    const modalBody = document.querySelector(".settings-modal-body") as HTMLElement;
    mockRect(main, { left: 0, top: 0, width: 800, height: 600 });
    mockRect(behindButton, { left: 120, top: 140, width: 160, height: 48 });
    mockRect(backdrop, { left: 0, top: 0, width: 800, height: 600 });
    mockRect(modal, { left: 80, top: 80, width: 360, height: 260 });
    mockRect(modalBody, { left: 110, top: 120, width: 300, height: 180 });
    Object.defineProperty(document, "elementsFromPoint", {
      configurable: true,
      value: vi.fn(() => [modalBody, modal, backdrop, behindButton, main, document.body])
    });

    const evidence = collectPageAnnotationEvidence({
      selection: { left: 140, top: 150, width: 40, height: 30 },
      appState: {
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "settings"
      }
    });

    expect(evidence.primaryTarget?.selector).toBe('section[aria-label="Settings"]');
    expect(evidence.elements.map((element) => element.selector)).not.toContain('[data-debug-id="behind-action"]');
  });
});
