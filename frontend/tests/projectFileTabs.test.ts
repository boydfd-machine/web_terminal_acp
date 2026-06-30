import { describe, expect, it } from "vitest";

import {
  MAX_PROJECT_FILE_TABS,
  PROJECT_FILE_TABS_STORAGE_KEY,
  closeProjectFileTab,
  nextProjectFileTab,
  openProjectFileTab,
  projectFileSwitchCandidates,
  projectFileTabKey,
  projectFileTabsForContext,
  readProjectFileTabsState,
  selectProjectFileTab,
  writeProjectFileTabsState,
  type ProjectFileTabContext,
  type ProjectFileTabsState
} from "../src/projectFileTabs";
import type { ProjectFileEntry } from "../src/types";

const context: ProjectFileTabContext = {
  clientId: "client-1",
  projectPath: "/workspace/project",
  browseRoot: null
};

function file(path: string, overrides: Partial<ProjectFileEntry> = {}): ProjectFileEntry {
  const slash = path.lastIndexOf("/");
  return {
    name: slash === -1 ? path : path.slice(slash + 1),
    path,
    kind: "file",
    size: 10,
    mtime: null,
    ...overrides
  };
}

describe("project file tabs", () => {
  it("reads and writes browser storage with a safe fallback", () => {
    let state: ProjectFileTabsState = { tabs: [], activeKey: null };
    state = openProjectFileTab(state, context, file("README.md"), 3, 1);

    writeProjectFileTabsState(state);
    expect(readProjectFileTabsState()).toEqual(state);

    window.localStorage.setItem(PROJECT_FILE_TABS_STORAGE_KEY, "{broken");
    expect(readProjectFileTabsState()).toEqual({ tabs: [], activeKey: null });
  });

  it("keeps at most ten open files and refreshes an existing tab without duplicating it", () => {
    let state: ProjectFileTabsState = { tabs: [], activeKey: null };
    for (let index = 1; index <= MAX_PROJECT_FILE_TABS + 1; index += 1) {
      state = openProjectFileTab(state, context, file(`src/file-${index}.ts`), null, index);
    }

    expect(projectFileTabsForContext(state, context).map((tab) => tab.path)).toEqual([
      "src/file-2.ts",
      "src/file-3.ts",
      "src/file-4.ts",
      "src/file-5.ts",
      "src/file-6.ts",
      "src/file-7.ts",
      "src/file-8.ts",
      "src/file-9.ts",
      "src/file-10.ts",
      "src/file-11.ts"
    ]);
    expect(state.activeKey).toBe(projectFileTabKey(context, "src/file-11.ts"));

    state = openProjectFileTab(
      state,
      context,
      file("src/file-5.ts", { name: "renamed.ts", size: 42 }),
      7,
      20
    );

    const tabs = projectFileTabsForContext(state, context);
    expect(tabs).toHaveLength(MAX_PROJECT_FILE_TABS);
    expect(tabs.filter((tab) => tab.path === "src/file-5.ts")).toHaveLength(1);
    expect(tabs.find((tab) => tab.path === "src/file-5.ts")).toMatchObject({
      name: "renamed.ts",
      line: 7,
      size: 42
    });
  });

  it("cycles tabs inside the active project context", () => {
    let state: ProjectFileTabsState = { tabs: [], activeKey: null };
    state = openProjectFileTab(state, context, file("README.md"), null, 1);
    state = openProjectFileTab(state, context, file("src/App.tsx"), null, 2);
    state = openProjectFileTab(state, {
      ...context,
      projectPath: "/other"
    }, file("other.txt"), null, 3);
    state = selectProjectFileTab(state, projectFileTabKey(context, "README.md"), 4);

    expect(nextProjectFileTab(state, context, projectFileTabKey(context, "README.md"))?.path).toBe("src/App.tsx");
    expect(nextProjectFileTab(state, context, projectFileTabKey(context, "src/App.tsx"))?.path).toBe("README.md");
  });

  it("builds switch candidates across projects for the active client", () => {
    let state: ProjectFileTabsState = { tabs: [], activeKey: null };
    state = openProjectFileTab(state, context, file("README.md"), null, 1);
    state = openProjectFileTab(state, {
      ...context,
      projectPath: "/other"
    }, file("src/App.tsx"), null, 3);
    state = openProjectFileTab(state, {
      ...context,
      clientId: "client-2",
      projectPath: "/workspace/project"
    }, file("client-2.ts"), null, 4);
    state = selectProjectFileTab(state, projectFileTabKey(context, "README.md"), 5);

    expect(projectFileSwitchCandidates(state, "client-1", "").map((tab) => ({
      path: tab.path,
      projectPath: tab.projectPath,
      active: tab.active
    }))).toEqual([
      { path: "README.md", projectPath: "/workspace/project", active: true },
      { path: "src/App.tsx", projectPath: "/other", active: false }
    ]);
    expect(projectFileSwitchCandidates(state, "client-1", "other").map((tab) => tab.path)).toEqual([
      "src/App.tsx"
    ]);
  });

  it("chooses a neighboring tab when the active tab closes", () => {
    let state: ProjectFileTabsState = { tabs: [], activeKey: null };
    state = openProjectFileTab(state, context, file("README.md"), null, 1);
    state = openProjectFileTab(state, context, file("src/App.tsx"), null, 2);
    state = openProjectFileTab(state, context, file("src/main.tsx"), null, 3);

    const result = closeProjectFileTab(state, projectFileTabKey(context, "src/App.tsx"), context, 4);

    expect(result.nextActiveTab?.path).toBe("src/main.tsx");
    expect(projectFileTabsForContext(result.state, context).map((tab) => tab.path)).toEqual([
      "README.md",
      "src/main.tsx"
    ]);
  });
});
