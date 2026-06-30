import { act } from "react";
import { describe, expect, it } from "vitest";

import * as s from "./appTestHarness";

const container = s.currentContainer;

describe("App project switching", () => {
  it("keeps Kanban project selection synced with Files and Terminal", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);

    const otherProject = await s.waitForProjectCard("/other");
    act(() => {
      otherProject.click();
    });

    await s.waitForSelectedProject("/other");
    await s.waitForTerminalPaneWindow("window-3");
    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(window.location.search).toContain("project_path=%2Fother");
    expect(window.location.search).toContain("window_id=window-3");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector(".project-file-preview")?.textContent).toContain("/other");
    expect(window.location.pathname).toBe("/clients/client-1/files");
    expect(window.location.search).toContain("project_path=%2Fother");
    expect(window.location.search).toContain("window_id=window-3");

    const terminalButton = await s.waitForButtonText("Terminal", true);
    act(() => terminalButton.click());
    await s.waitForTerminalPaneWindow("window-3");
  });
});
