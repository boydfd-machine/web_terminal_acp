import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { container, jsonResponse, renderSettingsModal, waitFor } from "./settingsModalHarness";

function setSearchValue(target: HTMLInputElement, value: string): Promise<void> {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  return act(async () => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("System agent config search", () => {
  it("filters system skills by search query", async () => {
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
                { id: "deep-research", name: "Deep Research", enabled: true, path: "/skills/deep-research", origin: "system_config" },
                { id: "image-to-ppt", name: "Image to PPT", enabled: false, path: "/skills/image-to-ppt", origin: "system_builtin" }
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
      expect(container?.textContent).toContain("Deep Research");
      expect(container?.textContent).toContain("Image to PPT");
    });
    const searchInput = container?.querySelector<HTMLInputElement>(".system-config-search input");
    expect(searchInput).toBeInstanceOf(HTMLInputElement);
    await setSearchValue(searchInput as HTMLInputElement, "image");

    expect(container?.textContent).not.toContain("Deep Research");
    expect(container?.textContent).toContain("Image to PPT");

    await setSearchValue(searchInput as HTMLInputElement, "missing");
    expect(container?.textContent).toContain("没有匹配项。");
  });

  it("filters system skill detail files by search query", async () => {
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
            { path: "SKILL.md", kind: "file", size: 27 },
            { path: "scripts", kind: "directory", size: null },
            { path: "scripts/run.sh", kind: "file", size: 8 }
          ],
          files: [
            { path: "SKILL.md", content: "---\nname: Review Helper\n---\n", size: 27, editable: true },
            { path: "scripts/run.sh", content: "echo ok\n", size: 8, editable: true }
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
      expect(container?.textContent).toContain("Review Helper");
    });
    const rowButton = container?.querySelector(".system-config-item-content");
    expect(rowButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (rowButton as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("scripts");
      expect(container?.textContent).toContain("run.sh");
    });
    const searchInput = container?.querySelector<HTMLInputElement>(".system-config-file-search input");
    expect(searchInput).toBeInstanceOf(HTMLInputElement);
    await setSearchValue(searchInput as HTMLInputElement, "run.sh");

    await waitFor(() => {
      expect(container?.textContent).toContain("run.sh");
      expect(container?.textContent).not.toContain("SKILL.md");
    });
  });
});
