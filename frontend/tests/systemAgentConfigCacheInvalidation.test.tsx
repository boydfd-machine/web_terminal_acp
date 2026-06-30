import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { getSettingsQueryClient, container, jsonResponse, renderSettingsModal, waitFor } from "./settingsModalHarness";

describe("System agent config cache invalidation", () => {
  it("invalidates dispatch config caches when toggling system MCP defaults", async () => {
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
              items: [{
                id: "web-terminal-acp-mcp",
                name: "web-terminal-acp-mcp",
                enabled: true,
                path: null,
                origin: "system_builtin"
              }]
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
              items: [{
                id: "web-terminal-acp-mcp",
                name: "web-terminal-acp-mcp",
                enabled: false,
                path: null,
                origin: "system_builtin"
              }]
            }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "system-mcp" });
    const queryClient = getSettingsQueryClient();
    queryClient.setQueryData(["client-system-agent-config", "client-1"], {
      agent: "system",
      sections: [
        { id: "skills", name: "System Skills", items: [] },
        {
          id: "mcp",
          name: "System MCP Servers",
          items: [{ id: "web-terminal-acp-mcp", name: "web-terminal-acp-mcp", enabled: true, path: null }]
        }
      ]
    });
    queryClient.setQueryData(["client-agent-config", "client-1", "codex", "builtin/page-review"], {
      agent: "codex",
      sections: [
        { id: "skills", name: "Skills", items: [] },
        { id: "mcp", name: "MCP Servers", items: [] }
      ]
    });
    queryClient.setQueryData(["agent-profile-config", "client-1", "builtin/page-review", "codex"], {
      agent: "codex",
      sections: [
        { id: "skills", name: "Skills", items: [] },
        { id: "mcp", name: "MCP Servers", items: [] }
      ]
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("web-terminal-acp-mcp");
    });
    const toggle = container?.querySelector('input[aria-label="禁用 web-terminal-acp-mcp"]');
    expect(toggle).toBeInstanceOf(HTMLInputElement);
    await act(async () => {
      (toggle as HTMLInputElement).click();
    });

    await waitFor(() => {
      expect(queryClient.getQueryState(["client-system-agent-config", "client-1"])?.isInvalidated).toBe(true);
      expect(
        queryClient.getQueryState(["client-agent-config", "client-1", "codex", "builtin/page-review"])?.isInvalidated
      ).toBe(true);
      expect(
        queryClient.getQueryState(["agent-profile-config", "client-1", "builtin/page-review", "codex"])?.isInvalidated
      ).toBe(true);
    });
  });
});
