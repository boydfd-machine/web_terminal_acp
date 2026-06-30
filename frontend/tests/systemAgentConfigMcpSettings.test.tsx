import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  container,
  jsonResponse,
  renderSettingsModal,
  setValue as setFormValue,
  waitFor
} from "./settingsModalHarness";

describe("System agent config MCP settings", () => {
  it("saves system MCP JSON from Settings", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/mcp") {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({
          id: "system-echo",
          server: { type: "stdio", command: "pwd", args: ["ok"] },
          enabled: true
        });
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            {
              id: "mcp",
              name: "System MCP Servers",
              items: [{ id: "system-echo", name: "system-echo", enabled: true, path: null }]
            }
          ]
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
      expect(container?.querySelector(".system-config-editor")).not.toBeNull();
    });
    const idInput = container?.querySelector('.system-config-editor input[placeholder="filesystem"]');
    const jsonInput = container?.querySelector(".system-config-json textarea");
    expect(idInput).toBeInstanceOf(HTMLInputElement);
    expect(jsonInput).toBeInstanceOf(HTMLTextAreaElement);

    act(() => {
      setFormValue(idInput as HTMLInputElement, "system-echo");
      setFormValue(jsonInput as HTMLTextAreaElement, "{\"type\":\"stdio\",\"command\":\"pwd\",\"args\":[\"ok\"]}");
    });
    const saveButton = container?.querySelector(".system-config-editor button");
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/mcp"),
      expect.objectContaining({ method: "PUT" })
    );
  });
});
