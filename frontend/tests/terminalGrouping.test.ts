import { describe, expect, it } from "vitest";

import {
  buildProjectTimeTopicSwitcherTree,
  buildProjectTopicSwitcherTree,
  buildTerminalSwitcherTree,
  buildTimeTopicSwitcherTree,
  buildTopicSwitcherTree,
  canCreateWindowAtGroupNode,
  collectCreatableProjectPaths,
  createWindowInputForGroupNode,
  findPathToSwitcherWindow,
  projectGroupLabel,
  projectPathFromRuntimeTags,
  terminalGroupingModeHasProjectRoot,
  type SwitcherGroupNode
} from "../src/terminalGrouping";
import type { TreeFolder } from "../src/types";

const sampleFolders: TreeFolder[] = [
  {
    id: "folder-1",
    name: "主题",
    path: "/主题",
    folders: [],
    windows: [
      {
        id: "w1",
        title: "Terminal A",
        status: "ACTIVE",
        runtime_tags: ["/workspace/project-a"],
        work_status: { state: "WORKING", label: "Working", color: "orange" },
        created_at: "2026-05-24T10:00:00Z"
      }
    ]
  },
  {
    id: "folder-2",
    name: "其他",
    path: "/其他",
    folders: [],
    windows: [
      {
        id: "w2",
        title: "Terminal B",
        status: "ACTIVE",
        runtime_tags: ["/workspace/project-b"],
        work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
        created_at: "2026-05-24T11:00:00Z"
      }
    ]
  }
];

describe("terminalGrouping", () => {
  it("extracts absolute project path from runtime tags", () => {
    expect(projectPathFromRuntimeTags(["codex", "/workspace/demo"])).toBe("/workspace/demo");
    expect(projectPathFromRuntimeTags(["codex"])).toBe("/未指定");
  });

  it("uses project path until a summary display name exists", () => {
    const summaries = new Map([
      [
        "/workspace/project-a",
        {
          project_path: "/workspace/project-a",
          display_name: "终端编排",
          status: "SUCCEEDED",
          last_error: null,
          updated_at: "2026-05-24T12:00:00Z"
        }
      ]
    ]);

    expect(projectGroupLabel("/workspace/project-a", summaries)).toBe("终端编排");
    expect(projectGroupLabel("/workspace/project-b", summaries)).toBe("/workspace/project-b");
  });

  it("builds project-topic hierarchy", () => {
    const tree = buildProjectTopicSwitcherTree(sampleFolders, new Map(), "");
    expect(tree).toHaveLength(2);
    expect(tree[0]?.projectPath).toBe("/workspace/project-a");
    expect(tree[0]?.children[0]?.label).toBe("主题");
    expect(tree[0]?.children[0]?.children[0]?.type).toBe("window");
  });

  it("builds topic hierarchy", () => {
    const tree = buildTopicSwitcherTree(sampleFolders, "");
    expect(tree).toHaveLength(2);
    expect(tree[0]?.key).toBe("topic:/主题");
    expect(tree[0]?.label).toBe("主题");
    expect(tree[0]?.children[0]?.type).toBe("window");
  });

  it("builds time-topic hierarchy", () => {
    const tree = buildTimeTopicSwitcherTree(sampleFolders, "");
    const monthGroup = tree[0] as SwitcherGroupNode;
    const dayGroup = monthGroup.children[0] as SwitcherGroupNode;
    const topicGroup = dayGroup.children[0] as SwitcherGroupNode;

    expect(monthGroup.key).toBe("time-topic:time:2026-05");
    expect(monthGroup.label).toBe("2026-05");
    expect(dayGroup.key).toBe("time-topic:time:2026-05:05-24");
    expect(dayGroup.label).toBe("05-24");
    expect(topicGroup.key).toBe("time-topic:time:2026-05:05-24:topic:/主题");
    expect(topicGroup.label).toBe("主题");
    expect(topicGroup.children[0]?.type).toBe("window");
  });

  it("builds project-time-topic hierarchy", () => {
    const tree = buildProjectTimeTopicSwitcherTree(sampleFolders, new Map(), "");
    const projectGroup = tree[0] as SwitcherGroupNode;
    const monthGroup = projectGroup.children[0] as SwitcherGroupNode;
    const dayGroup = monthGroup.children[0] as SwitcherGroupNode;
    const topicGroup = dayGroup.children[0] as SwitcherGroupNode;

    expect(projectGroup.key).toBe("project-time-topic:/workspace/project-a");
    expect(projectGroup.projectPath).toBe("/workspace/project-a");
    expect(monthGroup.key).toBe("project-time-topic:/workspace/project-a:time:2026-05");
    expect(dayGroup.key).toBe("project-time-topic:/workspace/project-a:time:2026-05:05-24");
    expect(topicGroup.key).toBe("project-time-topic:/workspace/project-a:time:2026-05:05-24:topic:/主题");
    expect(topicGroup.children[0]?.type).toBe("window");
  });

  it("builds all terminal grouping modes", () => {
    expect(buildTerminalSwitcherTree(sampleFolders, "project-topic", new Map(), "")).toHaveLength(2);
    expect(buildTerminalSwitcherTree(sampleFolders, "topic", new Map(), "")).toHaveLength(2);
    expect(buildTerminalSwitcherTree(sampleFolders, "time-topic", new Map(), "")[0]?.label).toBe("2026-05");
    expect(buildTerminalSwitcherTree(sampleFolders, "project-time-topic", new Map(), "")[0]?.projectPath).toBe(
      "/workspace/project-a"
    );
  });

  it("builds create-window input for project and topic groups", () => {
    const tree = buildProjectTopicSwitcherTree(sampleFolders, new Map(), "");
    const projectGroup = tree[0] as SwitcherGroupNode;
    const topicGroup = projectGroup.children[0] as SwitcherGroupNode;

    expect(canCreateWindowAtGroupNode(projectGroup)).toBe(true);
    expect(createWindowInputForGroupNode(projectGroup)).toEqual({
      cwd: "/workspace/project-a"
    });
    expect(canCreateWindowAtGroupNode(topicGroup)).toBe(false);
    expect(createWindowInputForGroupNode(topicGroup)).toEqual({});
  });

  it("marks project-root grouping modes", () => {
    expect(terminalGroupingModeHasProjectRoot("project-topic")).toBe(true);
    expect(terminalGroupingModeHasProjectRoot("project-time-topic")).toBe(true);
    expect(terminalGroupingModeHasProjectRoot("topic")).toBe(false);
    expect(terminalGroupingModeHasProjectRoot("time-topic")).toBe(false);
  });

  it("collects only concrete project paths for project terminal creation", () => {
    const folders: TreeFolder[] = [
      ...sampleFolders,
      {
        id: "folder-3",
        name: "未指定",
        path: "/未指定主题",
        folders: [],
        windows: [
          {
            id: "w3",
            title: "Terminal C",
            status: "ACTIVE",
            runtime_tags: [],
            work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
            created_at: "2026-05-24T12:00:00Z"
          }
        ]
      }
    ];

    expect(collectCreatableProjectPaths(folders)).toEqual([
      "/workspace/project-a",
      "/workspace/project-b"
    ]);
  });

  it("finds path to a window in project-topic tree", () => {
    const tree = buildProjectTopicSwitcherTree(sampleFolders, new Map(), "");
    expect(findPathToSwitcherWindow(tree, "w1")).toEqual([
      "project:/workspace/project-a",
      "project-topic:/workspace/project-a:topic:/主题",
      "window:w1"
    ]);
  });
});
