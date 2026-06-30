import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { container, jsonResponse, renderSettingsModal, setValue, waitFor } from "./settingsModalHarness";

describe("System agent built-in config defaults", () => {
  it("shows system built-in skills as source rows with editable defaults", async () => {
    let skillOverridden = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [
                skillOverridden
                  ? { id: "pr-review", name: "custom-pr-review", enabled: true, path: "/tmp/pr-review", origin: "system_config", overridden: true }
                  : { id: "pr-review", name: "pr-review", enabled: true, path: null, origin: "system_builtin", overridden: false },
                { id: "review-helper", name: "Review Helper", enabled: true, path: null, origin: "system_config" }
              ]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/pr-review") {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ enabled: false }));
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [
                { id: "pr-review", name: "pr-review", enabled: false, path: null, origin: "system_builtin" },
                { id: "review-helper", name: "Review Helper", enabled: true, path: null, origin: "system_config" }
              ]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/pr-review/detail") {
        return jsonResponse({
          id: "pr-review",
          name: "pr-review",
          enabled: true,
          path: null,
          origin: "system_builtin",
          editable: true,
          overridden: false,
          entries: [{ path: "SKILL.md", kind: "file", size: 24 }],
          files: [{ path: "SKILL.md", content: "---\nname: pr-review\n---\n", size: 24, editable: true }]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/pr-review/files") {
        expect(init?.method).toBe("PATCH");
        expect(JSON.parse(String(init?.body))).toEqual({ path: "SKILL.md", content: "custom built-in\n" });
        skillOverridden = true;
        return jsonResponse({
          id: "pr-review",
          name: "custom-pr-review",
          enabled: true,
          path: "/tmp/pr-review",
          origin: "system_config",
          editable: true,
          overridden: true,
          entries: [{ path: "SKILL.md", kind: "file", size: 16 }],
          files: [{ path: "SKILL.md", content: "custom built-in\n", size: 16, editable: true }]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/pr-review/reset") {
        expect(init?.method).toBe("POST");
        skillOverridden = false;
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [
                { id: "pr-review", name: "pr-review", enabled: true, path: null, origin: "system_builtin", overridden: false },
                { id: "review-helper", name: "Review Helper", enabled: true, path: null, origin: "system_config" }
              ]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal();
    const skillTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("系统 Skill"));
    expect(skillTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (skillTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("pr-review");
      expect(container?.textContent).toContain("系统内置");
      expect(container?.textContent).toContain("系统配置");
    });
    const rows = Array.from(container?.querySelectorAll(".system-config-item") ?? []);
    const builtInRow = rows.find((row) => row.textContent?.includes("pr-review"));
    const managedRow = rows.find((row) => row.textContent?.includes("Review Helper"));
    expect(builtInRow).toBeInstanceOf(HTMLLIElement);
    expect(managedRow).toBeInstanceOf(HTMLLIElement);
    const builtInToggle = builtInRow?.querySelector("input");
    expect(builtInToggle).toBeInstanceOf(HTMLInputElement);
    expect((builtInToggle as HTMLInputElement).disabled).toBe(false);
    expect(builtInRow?.querySelector('button[aria-label="下载 pr-review"]')).toBeInstanceOf(HTMLButtonElement);
    expect(builtInRow?.querySelector('button[aria-label="删除 pr-review"]')).toBeNull();
    expect(managedRow?.querySelectorAll(".system-config-icon-button")).toHaveLength(2);
    await act(async () => {
      (builtInToggle as HTMLInputElement).click();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/skills/pr-review"),
      expect.objectContaining({ method: "PATCH" })
    );

    const rowButton = builtInRow?.querySelector(".system-config-item-content");
    expect(rowButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (rowButton as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("Editable");
    });
    const sourceModeButton = Array.from(container?.querySelectorAll(".workspace-mode-toggle button") ?? [])
      .find((button) => button.textContent?.includes("Source"));
    expect(sourceModeButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (sourceModeButton as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.querySelector(".system-config-file-editor textarea")).toBeInstanceOf(HTMLTextAreaElement);
    });
    const editor = container?.querySelector(".system-config-file-editor textarea");
    setValue(editor as HTMLTextAreaElement, "custom built-in\n");
    const saveButton = container?.querySelector('button[aria-label="保存 SKILL.md"]');
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/system-agent-config/skills/pr-review/files"),
        expect.objectContaining({ method: "PATCH" })
      );
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("已覆盖");
      const updatedRows = Array.from(container?.querySelectorAll(".system-config-item") ?? []);
      const overriddenRow = updatedRows.find((row) => row.textContent?.includes("custom-pr-review"));
      expect(overriddenRow?.querySelector('button[aria-label="下载 custom-pr-review"]')).toBeInstanceOf(HTMLButtonElement);
      expect(overriddenRow?.querySelector('button[aria-label="删除 custom-pr-review"]')).toBeNull();
    });
    const resetButton = container?.querySelector('button[aria-label="恢复出厂设置"]');
    expect(resetButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (resetButton as HTMLButtonElement).click();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/skills/pr-review/reset"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("shows system built-in MCP servers as source rows with editable defaults", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            {
              id: "mcp",
              name: "System MCP Servers",
              items: [
                { id: "web-terminal-acp-mcp", name: "web-terminal-acp-mcp", enabled: true, path: null, origin: "system_builtin" },
                { id: "system-echo", name: "system-echo", enabled: true, path: null, origin: "system_config" }
              ]
            }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/mcp/web-terminal-acp-mcp") {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ enabled: false }));
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            {
              id: "mcp",
              name: "System MCP Servers",
              items: [
                { id: "web-terminal-acp-mcp", name: "web-terminal-acp-mcp", enabled: false, path: null, origin: "system_builtin" },
                { id: "system-echo", name: "system-echo", enabled: true, path: null, origin: "system_config" }
              ]
            }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/mcp/web-terminal-acp-mcp/detail") {
        return jsonResponse({
          id: "web-terminal-acp-mcp",
          name: "web-terminal-acp-mcp",
          enabled: true,
          path: null,
          origin: "system_builtin",
          editable: true,
          overridden: false,
          server: { type: "stdio", command: "python" },
          tools: []
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal();
    const mcpTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("系统 MCP"));
    expect(mcpTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (mcpTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("web-terminal-acp-mcp");
      expect(container?.textContent).toContain("系统内置");
    });
    const rows = Array.from(container?.querySelectorAll(".system-config-item") ?? []);
    const builtInRow = rows.find((row) => row.textContent?.includes("web-terminal-acp-mcp"));
    const managedRow = rows.find((row) => row.textContent?.includes("system-echo"));
    const builtInToggle = builtInRow?.querySelector("input");
    expect(builtInToggle).toBeInstanceOf(HTMLInputElement);
    expect((builtInToggle as HTMLInputElement).disabled).toBe(false);
    expect(builtInRow?.querySelectorAll(".system-config-icon-button")).toHaveLength(0);
    expect(managedRow?.querySelectorAll(".system-config-icon-button")).toHaveLength(1);
    await act(async () => {
      (builtInToggle as HTMLInputElement).click();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/mcp/web-terminal-acp-mcp"),
      expect.objectContaining({ method: "PATCH" })
    );

    const rowButton = builtInRow?.querySelector(".system-config-item-content");
    expect(rowButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (rowButton as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("Editable");
      expect(container?.querySelector('button[aria-label="恢复出厂设置"]')).toBeInstanceOf(HTMLButtonElement);
    });
  });
});
