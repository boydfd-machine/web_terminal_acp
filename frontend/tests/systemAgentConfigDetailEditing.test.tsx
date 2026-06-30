import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { buttonByAriaLabel, container, jsonResponse, renderSettingsModal, setValue, waitFor } from "./settingsModalHarness";

describe("System agent config detail editing", () => {
  it("opens system skill detail and saves editable files", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{ id: "review-helper", name: "Review Helper", enabled: true, path: null, origin: "system_config" }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/review-helper/detail") {
        return jsonResponse({
          id: "review-helper",
          name: "Review Helper",
          enabled: true,
          path: "/tmp/review-helper",
          origin: "system_config",
          editable: true,
          entries: [
            { path: "SKILL.md", kind: "file", size: 34 },
            { path: "scripts", kind: "directory", size: null },
            { path: "scripts/run.sh", kind: "file", size: 8 }
          ],
          files: [
            { path: "SKILL.md", content: "---\nname: Review Helper\n---\n", size: 27, editable: true },
            { path: "scripts/run.sh", content: "echo ok\n", size: 8, editable: true }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/review-helper/files") {
        expect(init?.method).toBe("PATCH");
        expect(JSON.parse(String(init?.body))).toEqual({ path: "SKILL.md", content: "updated skill\n" });
        return jsonResponse({
          id: "review-helper",
          name: "Review Helper",
          enabled: true,
          path: "/tmp/review-helper",
          origin: "system_config",
          editable: true,
          entries: [{ path: "SKILL.md", kind: "file", size: 14 }],
          files: [{ path: "SKILL.md", content: "updated skill\n", size: 14, editable: true }]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal();
    const skillTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("系统 Skill"));
    act(() => {
      (skillTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Review Helper");
    });
    const rowButton = container?.querySelector(".system-config-item-content");
    expect(rowButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (rowButton as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("scripts");
      expect(container?.textContent).toContain("run.sh");
      expect(container?.textContent).toContain("Review Helper");
      expect(container?.querySelector(".system-config-markdown-preview")).not.toBeNull();
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
    act(() => {
      setValue(editor as HTMLTextAreaElement, "updated skill\n");
    });
    const saveButton = buttonByAriaLabel("保存 SKILL.md");
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/skills/review-helper/files"),
      expect.objectContaining({ method: "PATCH" })
    );
  });
});
