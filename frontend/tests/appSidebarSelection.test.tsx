import { act } from "react";
import { describe, expect, it, vi } from "vitest";

const { projectFileTreeUnmounts } = vi.hoisted(() => ({
  projectFileTreeUnmounts: new Map<string, number>()
}));

vi.mock("../src/components/ProjectFilesView", async () => {
  const React = await import("react");
  const actual = await vi.importActual<typeof import("../src/components/ProjectFilesView")>(
    "../src/components/ProjectFilesView"
  );

  return {
    ...actual,
    ProjectFileTreePanel: (props: {
      selectedPath?: string | null;
      onSelectEntry?: (entry: {
        name: string;
        path: string;
        kind: "file";
        size: number | null;
        mtime: number | null;
      }) => void;
    }) => {
      const [open, setOpen] = React.useState(false);
      React.useEffect(() => {
        return () => {
          projectFileTreeUnmounts.set(
            "project-file-tree",
            (projectFileTreeUnmounts.get("project-file-tree") ?? 0) + 1
          );
        };
      }, []);

      return React.createElement(
        "div",
        { "data-testid": "project-file-tree-panel" },
        React.createElement(
          "span",
          { "data-testid": "project-file-tree-selected-path" },
          props.selectedPath ?? ""
        ),
        React.createElement(
          "button",
          {
            "data-testid": "project-file-tree-open-button",
            type: "button",
            onClick: () => setOpen(true)
          },
          "Open src"
        ),
        React.createElement(
          "button",
          {
            "data-testid": "project-file-tree-file-button",
            type: "button",
            onClick: () => props.onSelectEntry?.({
              name: "README.md",
              path: "docs/README.md",
              kind: "file",
              size: 10,
              mtime: null
            })
          },
          "Open file"
        ),
        React.createElement(
          "button",
          {
            "data-testid": "project-file-tree-app-button",
            type: "button",
            onClick: () => props.onSelectEntry?.({
              name: "App.tsx",
              path: "src/App.tsx",
              kind: "file",
              size: 20,
              mtime: null
            })
          },
          "Open App"
        ),
        open
          ? React.createElement("span", { "data-testid": "project-file-tree-open-state" }, "src open")
          : null
      );
    }
  };
});

import * as s from "./appTestHarness";

const container = s.currentContainer;

function projectSectionButton(): HTMLButtonElement {
  const button = Array.from(container()?.querySelectorAll(".project-file-mode-sidebar .section-collapse-button") ?? []).find(
    (candidate): candidate is HTMLButtonElement => candidate instanceof HTMLButtonElement && candidate.textContent?.includes("Projects") === true
  );
  expect(button).toBeInstanceOf(HTMLButtonElement);
  return button as HTMLButtonElement;
}

describe("App new terminal shortcut", () => {
  it("allows missing window recovery for the visible route-selected terminal", async () => {
    s.renderApp();
    await s.waitForTerminalPaneWindow("window-1");

    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-allow-missing-window-recreate"
    )).toBe("true");

    await s.reportTerminalPaneStatus("connected");
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-allow-missing-window-recreate"
    )).toBe("false");
  });

  it("allows missing window recovery after the user explicitly selects a terminal", async () => {
    s.renderApp();
    await s.waitForTerminalPaneWindow("window-1");

    const otherProject = await s.waitForProjectCard("/other");
    act(() => {
      otherProject.click();
    });
    await s.waitForSelectedProject("/other");

    const otherWindowButton = await s.waitForButtonText("Other window", true);
    act(() => {
      otherWindowButton.click();
    });

    await s.waitForTerminalPaneWindow("window-3");
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-allow-missing-window-recreate"
    )).toBe("true");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-allow-missing-window-recreate"
    )).toBe("false");

    const terminalButton = await s.waitForButtonText("Terminal", true);
    act(() => terminalButton.click());
    await s.waitForTerminalPaneWindow("window-3");
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-allow-missing-window-recreate"
    )).toBe("true");

    await s.reportTerminalPaneStatus("connected");
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-allow-missing-window-recreate"
    )).toBe("false");
  });

  it("does not persist aux terminal position for a header click without dragging", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "A",
        code: "KeyA",
        altKey: true,
        shiftKey: true
      }));
    });
    await s.waitForRequests();

    const header = await s.waitForElement(".aux-terminal-header", (element): element is HTMLElement => element instanceof HTMLElement);
    act(() => {
      header.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        pointerId: 1,
        button: 0,
        clientX: 20,
        clientY: 20
      }));
      header.dispatchEvent(new PointerEvent("pointerup", {
        bubbles: true,
        cancelable: true,
        pointerId: 1,
        clientX: 20,
        clientY: 20
      }));
    });
    await s.waitForRequests();

    expect(window.localStorage.getItem(s.AUX_TERMINAL_POSITION_STORAGE_KEY)).toBeNull();
  });
  it("keeps the terminal pane mounted while switching workspace tabs", async () => {
    s.renderApp();
    await s.waitForTerminalPaneWindow("window-1");
    const initialPane = container()?.querySelector('[data-testid="terminal-pane"]');

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(s.terminalPaneUnmounts.get("terminal-pane") ?? 0).toBe(0);

    const terminalButton = await s.waitForButtonText("Terminal", true);
    act(() => terminalButton.click());
    await s.waitForTerminalPaneWindow("window-1");
    expect(container()?.querySelector('[data-testid="terminal-pane"]')).toBe(initialPane);

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(s.terminalPaneUnmounts.get("terminal-pane") ?? 0).toBe(0);

    act(() => terminalButton.click());
    await s.waitForTerminalPaneWindow("window-1");
    expect(container()?.querySelector('[data-testid="terminal-pane"]')).toBe(initialPane);
    expect(s.terminalPaneUnmounts.get("terminal-pane") ?? 0).toBe(0);
  });
  it("does not let a hidden terminal selection event leave project workspaces", async () => {
    s.renderApp();
    await s.waitForTerminalPaneWindow("window-1");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute("data-has-terminal-selection-handler")).toBe("false");
    await s.reportTerminalPaneSelection("window-3");
    expect(window.location.pathname).toBe("/clients/client-1/files");
    expect(container()?.querySelector(".project-file-preview")).not.toBeNull();

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute("data-has-terminal-selection-handler")).toBe("false");
    await s.reportTerminalPaneSelection("window-3");
    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(container()?.querySelector(".project-kanban-workspace")).not.toBeNull();
  });
  it("collapses the sidebar for Files but keeps it expanded for Kanban", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(window.location.pathname).toBe("/clients/client-1/files");
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(container()?.querySelector(".client-list")?.className).toContain("collapsed");
    expect(projectSectionButton().getAttribute("aria-expanded")).toBe("false");

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector(".client-list")?.className).not.toContain("collapsed");
    expect(projectSectionButton().getAttribute("aria-expanded")).toBe("true");
    expect(container()?.querySelector('button.terminal-project-card[title="/workspace"]')).not.toBeNull();
  });
  it("places kanban management and quick creation in the global projects sidebar", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    const sidebar = await s.waitForElement(".project-file-mode-sidebar", (element): element is HTMLElement => element instanceof HTMLElement);

    expect(sidebar.querySelector(".project-todo-management-bar")).not.toBeNull();
    expect(sidebar.querySelector(".project-todo-form-quick")).not.toBeNull();
    expect(sidebar.querySelector(".project-todo-quick-type select")).not.toBeNull();
    expect(container()?.querySelector(".project-kanban-workspace .project-todo-management-bar")).toBeNull();
    expect(container()?.querySelector(".project-kanban-workspace .project-todo-form-quick")).toBeNull();
  });
  it("opens the files workspace from a route", async () => {
    window.history.replaceState(null, "", "/clients/client-1/files?project_path=%2Fother&window_id=window-1");

    s.renderApp();

    for (let attempt = 0; attempt < 20; attempt += 1) {
      await s.waitForRequests();
      const preview = container()?.querySelector(".project-file-preview");
      if (preview?.textContent?.includes("/other")) {
        break;
      }
    }
    expect(container()?.querySelector(".project-file-preview")?.textContent).toContain("/other");
    expect(window.location.pathname).toBe("/clients/client-1/files");
    expect(window.location.search).toContain("project_path=%2Fother");
  });
  it("opens the kanban workspace from a route", async () => {
    window.history.replaceState(null, "", "/clients/client-1/kanban?project_path=%2Fother&window_id=window-1");

    s.renderApp();

    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    await s.waitForSelectedProject("/other");
    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(window.location.search).toContain("project_path=%2Fother");
  });
  it("opens and closes a kanban card detail route", async () => {
    window.history.replaceState(
      null,
      "",
      "/clients/client-1/kanban?project_path=%2Fworkspace&window_id=window-1&todo_id=todo-1"
    );

    s.renderApp();

    const detail = await s.waitForBodyElement(".project-todo-detail-dialog", (element): element is HTMLElement => (
      element instanceof HTMLElement
    ));
    expect(detail.getAttribute("data-project-todo-id")).toBe("todo-1");

    const closeButton = document.body.querySelector(".project-todo-detail-close");
    expect(closeButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (closeButton as HTMLButtonElement).click();
    });
    await s.waitForRequests();

    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(window.location.search).not.toContain("todo_id=");
  });
  it("writes kanban and card detail routes from workspace clicks", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(window.location.search).toContain("project_path=%2Fworkspace");

    const todoCard = await s.waitForElement(
      '.project-todo-card[data-project-todo-id="todo-1"] .project-todo-card-main',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => todoCard.click());
    await s.waitForBodyElement(".project-todo-detail-dialog", (element): element is HTMLElement => (
      element instanceof HTMLElement
    ));

    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(window.location.search).toContain("todo_id=todo-1");
  });
  it("writes files and selected file routes from workspace clicks", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(window.location.pathname).toBe("/clients/client-1/files");
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(window.location.search).toContain("window_id=window-1");

    const fileButton = await s.waitForElement(
      '[data-testid="project-file-tree-file-button"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => fileButton.click());
    await s.waitForRequests();

    expect(window.location.pathname).toBe("/clients/client-1/files");
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(window.location.search).toContain("file_path=docs%2FREADME.md");
  });
  it("opens a searchable file switcher with Alt+W and can switch across projects", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);

    const readmeButton = await s.waitForElement(
      '[data-testid="project-file-tree-file-button"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => readmeButton.click());
    await s.waitForRequests();

    const appButton = await s.waitForElement(
      '[data-testid="project-file-tree-app-button"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => appButton.click());
    await s.waitForRequests();

    const tabs = Array.from(container()?.querySelectorAll(".project-file-tabs [role='tab']") ?? []);
    expect(tabs.map((tab) => tab.textContent)).toEqual(["README.md", "App.tsx"]);
    expect(container()?.querySelector('[data-testid="project-file-tree-selected-path"]')?.textContent).toBe("src/App.tsx");

    if (projectSectionButton().getAttribute("aria-expanded") === "false") {
      act(() => {
        projectSectionButton().click();
      });
    }
    const otherProject = await s.waitForProjectCard("/other");
    act(() => {
      otherProject.click();
    });
    await s.waitForSelectedProject("/other");
    act(() => filesButton.click());
    const otherReadmeButton = await s.waitForElement(
      '[data-testid="project-file-tree-file-button"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => otherReadmeButton.click());
    await s.waitForRequests();
    expect(container()?.querySelector('[data-testid="project-file-tree-selected-path"]')?.textContent).toBe("docs/README.md");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "w",
        code: "KeyW",
        altKey: true
      }));
    });
    await s.waitForRequests();

    expect(container()?.querySelector(".terminal-switcher")).toBeNull();
    const switcher = await s.waitForElement(
      ".project-file-switcher",
      (element): element is HTMLElement => element instanceof HTMLElement
    );
    expect(switcher.textContent).toContain("/workspace");
    expect(switcher.textContent).toContain("/other");

    const workspaceAppButton = Array.from(container()?.querySelectorAll(".project-file-switcher-option") ?? []).find(
      (candidate): candidate is HTMLButtonElement => candidate instanceof HTMLButtonElement
        && candidate.textContent?.includes("App.tsx") === true
        && candidate.textContent?.includes("/workspace") === true
    );
    expect(workspaceAppButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      workspaceAppButton?.click();
    });
    await s.waitForRequests();

    expect(container()?.querySelector(".project-file-switcher")).toBeNull();
    await s.waitForSelectedProject("/workspace");
    expect(container()?.querySelector('[data-testid="project-file-tree-selected-path"]')?.textContent).toBe("src/App.tsx");
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(window.location.search).toContain("file_path=src%2FApp.tsx");
  });
  it("uses Alt+F in files mode to search only the selected project", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "f",
        code: "KeyF",
        altKey: true
      }));
    });

    const searchInput = await s.waitForElement(
      "#project-file-search-input",
      (element): element is HTMLInputElement => element instanceof HTMLInputElement
    );
    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
    act(() => {
      descriptor?.set?.call(searchInput, "needle");
      searchInput.dispatchEvent(new Event("input", { bubbles: true }));
      searchInput.closest("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await s.waitForRequests();

    const searchRequest = s.fetchMock.mock.calls.find(([input]) => (
      s.pathFor(input as RequestInfo | URL) === "/api/clients/client-1/projects/files/search"
      && s.searchParamFor(input as RequestInfo | URL, "q") === "needle"
    ));
    expect(searchRequest).toBeDefined();
    expect(s.searchParamFor(searchRequest?.[0] as RequestInfo | URL, "project_path")).toBe("/workspace");
    expect(s.searchParamFor(searchRequest?.[0] as RequestInfo | URL, "mode")).toBe("all");

    const resultButton = await s.waitForElement(
      ".project-file-search-modal .global-file-result button",
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => {
      resultButton.click();
    });
    await s.waitForRequests();

    expect(container()?.querySelector(".project-file-search-modal")).toBeNull();
    expect(window.location.search).toContain("project_path=%2Fworkspace");
    expect(window.location.search).toContain("file_path=src%2FApp.tsx");
    expect(window.location.search).toContain("line=4");
  });
  it("restores recent file tabs from browser storage and can locate a stored tab", async () => {
    window.history.replaceState(null, "", "/clients/client-1/files?project_path=%2Fworkspace&window_id=window-1");
    window.localStorage.setItem("web-terminal-acp:project-file-tabs", JSON.stringify({
      activeKey: JSON.stringify(["client-1", "/workspace", "", "docs/README.md"]),
      tabs: [
        {
          clientId: "client-1",
          projectPath: "/workspace",
          browseRoot: null,
          name: "README.md",
          path: "docs/README.md",
          size: 10,
          mtime: null,
          line: null,
          openedAt: 1,
          lastUsedAt: 1
        },
        {
          clientId: "client-1",
          projectPath: "/workspace",
          browseRoot: null,
          name: "App.tsx",
          path: "src/App.tsx",
          size: 20,
          mtime: null,
          line: null,
          openedAt: 2,
          lastUsedAt: 2
        }
      ]
    }));

    s.renderApp();
    await s.waitForElement(".project-file-tabs", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(Array.from(container()?.querySelectorAll(".project-file-tabs [role='tab']") ?? [])
      .map((tab) => tab.textContent)).toEqual(["README.md", "App.tsx"]);
    await s.waitForElement(
      '[data-testid="project-file-tree-selected-path"]',
      (element): element is HTMLElement => element instanceof HTMLElement && element.textContent === "docs/README.md"
    );

    const appTab = Array.from(container()?.querySelectorAll(".project-file-tabs [role='tab']") ?? [])
      .find((tab): tab is HTMLButtonElement => tab instanceof HTMLButtonElement && tab.textContent === "App.tsx");
    expect(appTab).toBeInstanceOf(HTMLButtonElement);
    act(() => appTab?.click());
    await s.waitForRequests();

    expect(container()?.querySelector('[data-testid="project-file-tree-selected-path"]')?.textContent).toBe("src/App.tsx");
    expect(window.location.search).toContain("file_path=src%2FApp.tsx");
  });
  it("clears a focused todo detail before opening Kanban", async () => {
    s.renderApp();
    await s.waitForTerminalPaneWindow("window-1");

    const todoLink = await s.waitForButtonText("Fix board dragTodo", true);
    act(() => todoLink.click());
    await s.waitForBodyElement(".project-todo-detail-dialog", (element): element is HTMLElement => (
      element instanceof HTMLElement
    ));

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    await s.waitForRequests();

    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
    expect(container()?.querySelector(".project-kanban-workspace .project-todo-card.selected")).toBeNull();
  });
  it("keeps the file tree mounted and stateful while switching workspace tabs", async () => {
    projectFileTreeUnmounts.clear();
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const filesButton = await s.waitForButtonText("Files", true);
    act(() => filesButton.click());
    const openButton = await s.waitForElement(
      '[data-testid="project-file-tree-open-button"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => openButton.click());
    expect(container()?.querySelector('[data-testid="project-file-tree-open-state"]')).not.toBeNull();

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => kanbanButton.click());
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(projectFileTreeUnmounts.get("project-file-tree") ?? 0).toBe(0);

    const terminalButton = await s.waitForButtonText("Terminal", true);
    act(() => terminalButton.click());
    await s.waitForTerminalPaneWindow("window-1");
    expect(projectFileTreeUnmounts.get("project-file-tree") ?? 0).toBe(0);

    act(() => filesButton.click());
    await s.waitForElement(".project-file-preview", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector('[data-testid="project-file-tree-open-state"]')).not.toBeNull();
    expect(projectFileTreeUnmounts.get("project-file-tree") ?? 0).toBe(0);
  });
  it("switches the active terminal when selecting another project", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const otherProject = await s.waitForProjectCard("/other");
    act(() => {
      otherProject.click();
    });

    await s.waitForSelectedProject("/other");
    await s.waitForButtonText("Other window", true);
    await s.waitForTerminalPaneWindow("window-3");
    expect(container()?.querySelector(".project-detail")).toBeNull();
  });
  it("opens project details from the explicit project detail button", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const otherProjectDetail = await s.waitForProjectDetailButton("/other");
    act(() => {
      otherProjectDetail.click();
    });

    await s.waitForSelectedProject("/other");
    await s.waitForElement(".project-detail", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(container()?.querySelector(".project-detail")?.textContent).toContain("/other");
    await s.waitForTerminalPaneWindow("window-3");
  });
  it("syncs the sidebar project again when a terminal is selected from that tree", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const otherProject = await s.waitForProjectCard("/other");
    act(() => {
      otherProject.click();
    });
    await s.waitForSelectedProject("/other");

    const otherWindowButton = await s.waitForButtonText("Other window", true);
    act(() => {
      otherWindowButton.click();
    });

    await s.waitForTerminalPaneWindow("window-3");
    await s.waitForSelectedProject("/other");
  });
  it("syncs the sidebar project when switching terminals through the switcher", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const otherProject = await s.waitForProjectCard("/other");
    act(() => {
      otherProject.click();
    });
    await s.waitForSelectedProject("/other");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "w",
        code: "KeyW",
        altKey: true
      }));
    });

    const otherWindowButton = await s.waitForSwitcherWindowButton("Other window");
    act(() => {
      otherWindowButton.click();
    });

    await s.waitForTerminalPaneWindow("window-3");
    await s.waitForSelectedProject("/other");
  });
  it("shows recent terminal status from other projects in the switcher", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "w",
        code: "KeyW",
        altKey: true
      }));
    });

    const otherWindowButton = await s.waitForSwitcherWindowButtonText("Other window", "claude code");

    expect(otherWindowButton.textContent).toContain("claude code");
    expect(otherWindowButton.textContent).toContain("other");
    expect(otherWindowButton.querySelector(".work-status-dot")).not.toBeNull();
  });
});
