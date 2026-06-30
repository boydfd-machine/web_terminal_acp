import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { flushQueries, renderSettingsModal, waitFor } from "./settingsModalHarness";

beforeEach(() => {
  vi.useFakeTimers();
});

describe("Settings artifact plugin preview modal", () => {
  it("opens artifact plugin previews in a dedicated dialog", async () => {
    vi.useRealTimers();
    const templatePluginSource = {
      python_source: "ARTIFACT_KIND = \"demo_report\"\nLABEL = \"Demo Report\"\nDEFAULT_TITLE = \"Demo report\"",
      prompt_template: "Build {{ source_title }}",
      html_template: "<html><body>{{ content.title }}</body></html>",
      json_schema: {
        type: "object",
        required: ["title"],
        properties: { title: { type: "string" } }
      },
      preview_content_json: {
        title: "Demo preview"
      }
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/artifact-plugins" && init?.method === undefined) {
        return new Response(JSON.stringify({
          plugins: [
            {
              domain: "terminal",
              artifact_kind: "demo_report",
              label: "Demo Report",
              default_title: "Demo report",
              origin: "managed",
              editable: true,
              plugin_format: "template",
              downloadable: true
            }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/demo_report" && init?.method === undefined) {
        return new Response(JSON.stringify({
          domain: "terminal",
          artifact_kind: "demo_report",
          label: "Demo Report",
          default_title: "Demo report",
          origin: "managed",
          editable: true,
          plugin_format: "template",
          downloadable: true,
          ...templatePluginSource
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/preview/html" && init?.method === "POST") {
        return new Response("<html><body>Draft plugin preview</body></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" }
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });

    renderSettingsModal({ initialView: "artifacts" });
    await flushQueries();

    await waitFor(() => {
      expect(document.body.querySelector(".artifact-plugin-preview-panel")).toBeNull();
      expect(document.body.querySelector(".artifact-plugin-preview-modal")).toBeNull();
      const button = document.body.querySelector("button[aria-label='打开 artifact 预览']");
      expect(button).toBeInstanceOf(HTMLButtonElement);
      expect((button as HTMLButtonElement).disabled).toBe(false);
    });
    const openButton = document.body.querySelector("button[aria-label='打开 artifact 预览']");
    expect(openButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (openButton as HTMLButtonElement).click();
    });

    await waitFor(() => {
      const modal = document.body.querySelector(".artifact-plugin-preview-modal");
      expect(modal).toBeInstanceOf(HTMLElement);
      expect(modal?.querySelector("iframe[title='Artifact plugin preview']")).toBeInstanceOf(HTMLIFrameElement);
      expect((modal?.querySelector("iframe") as HTMLIFrameElement | null)?.srcdoc).toContain("Draft plugin preview");
    });

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    });

    await waitFor(() => {
      expect(document.body.querySelector(".artifact-plugin-preview-modal")).toBeNull();
      expect(document.body.querySelector(".settings-modal")).toBeInstanceOf(HTMLElement);
    });
  });

  it("uses the user preferred language for selected terminal preview sessions", async () => {
    vi.useRealTimers();
    const templatePluginSource = {
      python_source: "ARTIFACT_KIND = \"demo_report\"\nLABEL = \"Demo Report\"\nDEFAULT_TITLE = \"Demo report\"",
      prompt_template: "Build {{ source_title }}",
      html_template: "<html><body>{{ content.title }}</body></html>",
      json_schema: {
        type: "object",
        required: ["title"],
        properties: { title: { type: "string" } }
      },
      preview_content_json: {
        title: "Demo preview"
      },
      preview_content_json_by_locale: {
        en: {
          title: "Demo preview"
        },
        zh: {
          title: "中文预览"
        }
      }
    };
    const preview = {
      id: "preview-1",
      client_id: "client-1",
      window_id: "window-1",
      created_by_window_id: "window-1",
      status: "valid",
      draft_artifact_kind: "demo_report",
      title: "Demo Report preview",
      components_json: {},
      demo_content_json: { title: "中文预览" },
      rendered_content_json: { title: "中文预览" },
      display_html: null,
      last_error: null,
      created_at: "2026-06-06T00:00:00Z",
      updated_at: "2026-06-06T00:00:00Z",
      expires_at: "2026-06-07T00:00:00Z"
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/artifact-plugins" && init?.method === undefined) {
        return new Response(JSON.stringify({
          plugins: [
            {
              domain: "terminal",
              artifact_kind: "demo_report",
              label: "Demo Report",
              default_title: "Demo report",
              origin: "managed",
              editable: true,
              plugin_format: "template",
              downloadable: true
            }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/demo_report" && init?.method === undefined) {
        return new Response(JSON.stringify({
          domain: "terminal",
          artifact_kind: "demo_report",
          label: "Demo Report",
          default_title: "Demo report",
          origin: "managed",
          editable: true,
          plugin_format: "template",
          downloadable: true,
          ...templatePluginSource
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugin-previews" && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          client_id: "client-1",
          window_id: "window-1",
          title: "Demo Report preview",
          python_source: templatePluginSource.python_source,
          prompt_template: templatePluginSource.prompt_template,
          html_template: templatePluginSource.html_template,
          json_schema: templatePluginSource.json_schema,
          demo_content_json: templatePluginSource.preview_content_json_by_locale.zh
        });
        return new Response(JSON.stringify(preview), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugin-previews/preview-1/html" && init?.method === undefined) {
        return new Response("<html><body>中文预览</body></html>", { status: 200, headers: { "Content-Type": "text/html" } });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });

    renderSettingsModal({ initialView: "artifacts", selectedWindowId: "window-1" });
    await flushQueries();

    await waitFor(() => {
      expect(document.body.querySelector(".artifact-plugin-preview-panel")).toBeNull();
      expect(document.body.querySelector("button[aria-label='打开 artifact 预览']")).toBeInstanceOf(HTMLButtonElement);
    });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => (
        input.toString().includes("/api/artifact-plugin-previews/preview-1/html")
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([input]) => (
      input.toString().includes("/api/artifact-plugins/terminal/preview/html")
    ))).toBe(false);
  });
});
