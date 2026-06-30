import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ColumnViewToggle, ProjectTodoBoardToolbar } from "../src/components/ProjectTodoBoardToolbar";
import { defaultProjectTodoBoardFilters } from "../src/features/projectTodos/projectTodoBoardModel";
import {
  cssRuleBodies as readCssRuleBodies,
  cssRuleBody as readCssRuleBody,
  readFrontendCss
} from "./cssTestUtils";
import { todo } from "./projectTodoTestHarness";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
const stylesCss = readFrontendCss("src/styles.css");

function cssRuleBody(selector: string): string {
  return readCssRuleBody(stylesCss, selector);
}

function cssRuleBodies(selector: string): string {
  return readCssRuleBodies(stylesCss, selector);
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  document.body.replaceChildren();
  root = null;
});

describe("ProjectTodoBoardToolbar", () => {
  it("renders the board search input in the filter toolbar", () => {
    const onUpdateFilter = vi.fn();
    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <ProjectTodoBoardToolbar
          activeFilterCount={0}
          childFilterParent={null}
          filterOptions={{ assignees: ["codex"], tags: ["frontend"] }}
          filters={defaultProjectTodoBoardFilters()}
          groupingMode="flat"
          settingsOpen={false}
          viewSettings={{ progress: true, totals: true, participants: true }}
          onCollapseAll={() => {}}
          onCreateTodo={() => {}}
          onExpandAll={() => {}}
          onGroupingModeChange={() => {}}
          onResetFilters={() => {}}
          onResetChildFilter={() => {}}
          onSettingsOpenChange={() => {}}
          onUpdateFilter={onUpdateFilter}
          onViewSettingsChange={() => {}}
        />
      );
    });

    const searchInput = document.body.querySelector(".project-todo-board-search input");
    expect(searchInput).toBeInstanceOf(HTMLInputElement);
    expect((searchInput as HTMLInputElement).placeholder).toBe("Tasks, tags, terminals");
  });

  it("renders the current search filter value", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <ProjectTodoBoardToolbar
          activeFilterCount={1}
          childFilterParent={null}
          filterOptions={{ assignees: [], tags: [] }}
          filters={{ ...defaultProjectTodoBoardFilters(), search: "frontend" }}
          groupingMode="flat"
          settingsOpen={false}
          viewSettings={{ progress: true, totals: true, participants: true }}
          onCollapseAll={() => {}}
          onCreateTodo={() => {}}
          onExpandAll={() => {}}
          onGroupingModeChange={() => {}}
          onResetFilters={() => {}}
          onResetChildFilter={() => {}}
          onSettingsOpenChange={() => {}}
          onUpdateFilter={() => {}}
          onViewSettingsChange={() => {}}
        />
      );
    });

    const searchInput = document.body.querySelector(".project-todo-board-search input");
    expect(searchInput).toBeInstanceOf(HTMLInputElement);
    expect((searchInput as HTMLInputElement).value).toBe("frontend");
  });

  it("renders a removable child-card filter chip", () => {
    const onResetChildFilter = vi.fn();
    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <ProjectTodoBoardToolbar
          activeFilterCount={1}
          childFilterParent={{ ...todo, id: "todo-parent", title: "Parent feature" }}
          filterOptions={{ assignees: [], tags: [] }}
          filters={{ ...defaultProjectTodoBoardFilters(), parentTodoId: "todo-parent" }}
          groupingMode="flat"
          settingsOpen={false}
          viewSettings={{ progress: true, totals: true, participants: true }}
          onCollapseAll={() => {}}
          onCreateTodo={() => {}}
          onExpandAll={() => {}}
          onGroupingModeChange={() => {}}
          onResetFilters={() => {}}
          onResetChildFilter={onResetChildFilter}
          onSettingsOpenChange={() => {}}
          onUpdateFilter={() => {}}
          onViewSettingsChange={() => {}}
        />
      );
    });

    const filterButton = document.body.querySelector(".project-todo-board-child-filter") as HTMLButtonElement;
    expect(filterButton).toBeInstanceOf(HTMLButtonElement);
    expect(filterButton.textContent).toContain("Parent feature and child cards");

    act(() => filterButton.click());
    expect(onResetChildFilter).toHaveBeenCalled();
  });

  it("renders the column card/tree view control as a switch, not buttons", () => {
    const onChange = vi.fn();
    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(<ColumnViewToggle column="TODO" value="tree" onChange={onChange} />);
    });

    const toggle = document.body.querySelector(".project-todo-column-view-toggle");
    const switchInput = document.body.querySelector(".project-todo-column-view-toggle input[type='checkbox']");
    const buttons = document.body.querySelectorAll(".project-todo-column-view-toggle button");
    expect(buttons).toHaveLength(0);
    expect(switchInput).toBeInstanceOf(HTMLInputElement);
    expect((switchInput as HTMLInputElement).getAttribute("role")).toBe("switch");
    expect((switchInput as HTMLInputElement).checked).toBe(true);
    expect(toggle?.textContent).toContain("Cards");
    expect(toggle?.textContent).toContain("Tree");
    expect(toggle?.querySelector(".project-todo-column-view-toggle-label.active")?.textContent).toBe("Tree");
    expect(cssRuleBody(".project-todo-column-view-toggle input:checked")).toMatch(/background:\s*(#2196f3|var\(--skin-accent-strong\))/);

    act(() => (switchInput as HTMLInputElement).click());
    expect(onChange).toHaveBeenCalledWith("cards");
  });

  it("keeps desktop kanban columns clipped while card lists own vertical scrolling", () => {
    const workspaceRule = cssRuleBody(".project-kanban-workspace");
    const kanbanColumnRule = cssRuleBody(".project-kanban-workspace .project-todo-column");
    const cardListRules = cssRuleBodies(".project-todo-column-cards");

    expect(workspaceRule).toContain("overscroll-behavior-y: contain");
    expect(kanbanColumnRule).toContain("overflow: hidden");
    expect(kanbanColumnRule).not.toContain("overflow-y: auto");
    expect(cardListRules).toContain("overflow-y: auto");
    expect(cardListRules).toContain("overscroll-behavior-y: contain");
  });

  it("locks the app scroll root while side panels own scroll containment", () => {
    const rootRule = cssRuleBody("html,\nbody,\n#root");
    const sidePanelRule = cssRuleBody(".sidebar,\n.detail-panel");

    expect(rootRule).toContain("overflow: hidden");
    expect(rootRule).toContain("overscroll-behavior: none");
    expect(sidePanelRule).toContain("overflow-y: auto");
    expect(sidePanelRule).toContain("overscroll-behavior-y: contain");
  });
});
