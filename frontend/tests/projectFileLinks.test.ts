import { afterEach, describe, expect, it } from "vitest";

import {
  projectFileOpenRequestFromMarkdownUrl,
  projectFileRoutePath,
  type ProjectFileLinkContext
} from "../src/projectFileLinks";

const context: ProjectFileLinkContext = {
  clientId: "client-1",
  windowId: "window-1",
  projectPath: "/workspace/project",
  browseRoot: null,
  cwd: "/workspace/project"
};

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("project file markdown links", () => {
  it("turns relative file paths with line suffixes into files routes", () => {
    const request = projectFileOpenRequestFromMarkdownUrl("frontend/src/App.tsx:12", context);

    expect(request).toEqual({
      clientId: "client-1",
      windowId: "window-1",
      projectPath: "/workspace/project",
      browseRoot: null,
      path: "frontend/src/App.tsx",
      line: 12
    });
    expect(request === null ? null : projectFileRoutePath(request)).toBe(
      "/clients/client-1/files?project_path=%2Fworkspace%2Fproject&window_id=window-1&file_path=frontend%2Fsrc%2FApp.tsx&line=12"
    );
  });

  it("keeps worktree absolute paths under the browse root", () => {
    const request = projectFileOpenRequestFromMarkdownUrl(
      "/workspace/project/.worktrees/feature/frontend/src/App.tsx#L7",
      {
        ...context,
        browseRoot: "/workspace/project/.worktrees/feature",
        cwd: "/workspace/project/.worktrees/feature"
      }
    );

    expect(request).toEqual({
      clientId: "client-1",
      windowId: "window-1",
      projectPath: "/workspace/project",
      browseRoot: "/workspace/project/.worktrees/feature",
      path: "frontend/src/App.tsx",
      line: 7
    });
  });

  it("resolves absolute project paths outside the selected worktree against the main project", () => {
    expect(projectFileOpenRequestFromMarkdownUrl(
      "/workspace/project/backend/app.py:22:4",
      {
        ...context,
        browseRoot: "/workspace/project/.worktrees/feature",
        cwd: "/workspace/project/.worktrees/feature"
      }
    )).toEqual({
      clientId: "client-1",
      windowId: "window-1",
      projectPath: "/workspace/project",
      browseRoot: null,
      path: "backend/app.py",
      line: 22
    });
  });

  it("uses the current working directory for relative paths and supports query line numbers", () => {
    expect(projectFileOpenRequestFromMarkdownUrl("./hooks/useThing.ts?line=9", {
      ...context,
      cwd: "/workspace/project/frontend/src"
    })).toEqual({
      clientId: "client-1",
      windowId: "window-1",
      projectPath: "/workspace/project",
      browseRoot: null,
      path: "frontend/src/hooks/useThing.ts",
      line: 9
    });
  });

  it("resolves file URLs under the active project", () => {
    expect(projectFileOpenRequestFromMarkdownUrl("file:///workspace/project/frontend/src/App.tsx#L18", context)).toEqual({
      clientId: "client-1",
      windowId: "window-1",
      projectPath: "/workspace/project",
      browseRoot: null,
      path: "frontend/src/App.tsx",
      line: 18
    });
  });

  it("does not treat external URLs with ports as file line suffixes", () => {
    expect(projectFileOpenRequestFromMarkdownUrl("https://example.com:5173/foo", context)).toBeNull();
  });

  it("does not inherit files query params from the current location for plain relative links", () => {
    window.history.replaceState(
      null,
      "",
      "/clients/current/files?project_path=%2Fold&window_id=current-window&file_path=old.ts"
    );

    expect(projectFileOpenRequestFromMarkdownUrl("src/new.ts", {
      ...context,
      clientId: "client-2",
      windowId: "window-2",
      projectPath: "/workspace/new",
      cwd: "/workspace/new"
    })).toEqual({
      clientId: "client-2",
      windowId: "window-2",
      projectPath: "/workspace/new",
      browseRoot: null,
      path: "src/new.ts",
      line: null
    });
  });
});
