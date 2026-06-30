import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  container,
  flushQueries,
  jsonResponse,
  renderSettingsModal,
  setValue,
  waitFor
} from "./settingsModalHarness";

beforeEach(() => {
  vi.useFakeTimers();
});

function buttonByAriaLabel(label: string): HTMLButtonElement | null {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  return button instanceof HTMLButtonElement ? button : null;
}

function buttonByAriaLabelPrefix(prefix: string): HTMLButtonElement | null {
  return Array.from(container?.querySelectorAll("button[aria-label]") ?? [])
    .find((button): button is HTMLButtonElement =>
      button instanceof HTMLButtonElement && button.getAttribute("aria-label")?.startsWith(prefix) === true
    ) ?? null;
}

function promptButtonByText(label: string): HTMLButtonElement | null {
  const dialog = document.body.querySelector('[role="alertdialog"]');
  return Array.from(dialog?.querySelectorAll("button") ?? [])
    .find((button): button is HTMLButtonElement => button instanceof HTMLButtonElement && button.textContent === label)
    ?? null;
}

describe("SettingsModal", () => {
  it("manages project todo card types from settings", async () => {
    vi.useRealTimers();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/projects/todo-types" && init?.method === undefined) {
        expect(url.searchParams.get("project_path")).toBe("/workspace");
        return jsonResponse({
          todo_types: [
            {
              id: "default",
              scope: "system",
              client_id: null,
              project_path: null,
              name: "Default",
              description: "Default project todo card type.",
              agent: null,
              agent_profile_id: null,
              artifact_kinds: [],
              dispatch_template: null,
              created_at: "2026-06-05T00:00:00Z",
              updated_at: "2026-06-05T00:00:00Z"
            },
            {
              id: "bug",
              scope: "project",
              client_id: "client-1",
              project_path: "/workspace",
              name: "Project Bug",
              description: "Project scoped bug cards",
              agent: "codex",
              agent_profile_id: "bug-profile",
              artifact_kinds: [],
              dispatch_template: null,
              created_at: "2026-06-05T00:00:00Z",
              updated_at: "2026-06-05T00:00:00Z"
            }
          ]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({
          agent_clients: [{
            id: "codex",
            provider_id: "codex",
            label: "Codex",
            aliases: [],
            default_command: "codex",
            command_names: ["codex"],
            capabilities: { launch: true, client_config: true }
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles" && init?.method === undefined) {
        return jsonResponse({ profiles: [] });
      }
      if (url.pathname === "/api/artifact-plugins" && init?.method === undefined) {
        return jsonResponse({ plugins: [] });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "card-types", selectedProjectPath: "/workspace" });

    await waitFor(() => {
      expect(container?.textContent).toContain("卡片类型");
      expect(container?.textContent).toContain("Project Bug");
    });
    const projectRow = Array.from(container?.querySelectorAll(".project-todo-type-row.read-only") ?? [])
      .find((row) => row.textContent?.includes("Project Bug"));
    expect(projectRow).toBeInstanceOf(HTMLElement);
    expect(projectRow?.querySelector("button")).toBeNull();
  });

  it("manages artifact plugins from settings", async () => {
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
    let promptTemplate = templatePluginSource.prompt_template;
    let deleted = false;
    const artifactPlugins = () => ({
      plugins: deleted ? [] : [
        {
          domain: "terminal",
          artifact_kind: "agent_trace_graph",
          label: "Agent Trace Graph",
          default_title: "Agent trace graph",
          origin: "built_in",
          editable: false,
          plugin_format: "template",
          downloadable: true
        },
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
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/artifact-plugins" && init?.method === undefined) {
        return new Response(JSON.stringify(artifactPlugins()), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/agent_trace_graph" && init?.method === undefined) {
        return new Response(JSON.stringify({
          domain: "terminal",
          artifact_kind: "agent_trace_graph",
          label: "Agent Trace Graph",
          default_title: "Agent trace graph",
          origin: "built_in",
          editable: false,
          plugin_format: "template",
          downloadable: true,
          python_source: "ARTIFACT_KIND = \"agent_trace_graph\"",
          prompt_template: "Build {{ source_title }}",
          html_template: "<html><body>{{ content.task }}</body></html>",
          json_schema: {
            type: "object",
            required: ["task", "goals", "nodes", "edges"],
            properties: {
              task: { type: "string" },
              goals: { type: "array" },
              nodes: { type: "array" },
              edges: { type: "array" }
            }
          },
          preview_content_json: {
            task: "Trace preview",
            goals: [],
            nodes: [],
            edges: []
          },
          preview_content_json_by_locale: {
            en: {
              task: "Trace preview",
              goals: [],
              nodes: [],
              edges: []
            },
            zh: {
              task: "追踪预览",
              goals: [],
              nodes: [],
              edges: []
            }
          }
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/preview/html" && init?.method === "POST") {
        return new Response("<html><body>Draft plugin preview</body></html>", { status: 200, headers: { "Content-Type": "text/html" } });
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
          ...templatePluginSource,
          prompt_template: promptTemplate
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/demo_report" && init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        expect(body).toEqual({
          python_source: templatePluginSource.python_source,
          prompt_template: "Build updated {{ source_title }}",
          html_template: templatePluginSource.html_template,
          json_schema: templatePluginSource.json_schema,
          preview_content_json: templatePluginSource.preview_content_json
        });
        promptTemplate = body.prompt_template;
        return new Response(JSON.stringify({
          domain: "terminal",
          artifact_kind: "demo_report",
          label: "Demo Report",
          default_title: "Demo report",
          origin: "managed",
          editable: true,
          plugin_format: "template",
          downloadable: true,
          ...templatePluginSource,
          prompt_template: promptTemplate
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/artifact-plugins/terminal/demo_report" && init?.method === "DELETE") {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    renderSettingsModal({ initialView: "artifacts" });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("Agent Trace Graph");
      expect(container?.textContent).toContain("plugin.py");
      expect(container?.textContent).toContain("prompt.jinja");
      expect(container?.textContent).toContain("display.html.jinja");
      expect(container?.textContent).toContain("schema.json");
      expect(container?.textContent).toContain("preview.json");
    });
    await waitFor(() => {
      expect(container?.querySelector(".artifact-plugin-preview-panel")).toBeNull();
      expect(container?.querySelector("button[aria-label='打开 artifact 预览']")).toBeInstanceOf(HTMLButtonElement);
    });
    const builtInTextarea = container?.querySelector(".system-config-file-editor textarea");
    expect(builtInTextarea).toBeInstanceOf(HTMLTextAreaElement);
    expect((builtInTextarea as HTMLTextAreaElement).readOnly).toBe(true);

    const managedRow = Array.from(container?.querySelectorAll(".artifact-plugin-row") ?? [])
      .find((row) => row.textContent?.includes("demo_report"));
    expect(managedRow).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (managedRow as HTMLButtonElement).click();
    });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("plugin.py");
      expect(container?.textContent).toContain("prompt.jinja");
      expect(container?.textContent).toContain("display.html.jinja");
      expect(container?.textContent).toContain("schema.json");
      expect(container?.textContent).toContain("preview.json");
    });
    const promptFileButton = Array.from(container?.querySelectorAll(".artifact-plugin-file-list button") ?? [])
      .find((button) => button.textContent?.includes("prompt.jinja"));
    expect(promptFileButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (promptFileButton as HTMLButtonElement).click();
    });
    const promptTextarea = container?.querySelector(".system-config-file-editor textarea");
    expect(promptTextarea).toBeInstanceOf(HTMLTextAreaElement);
    expect((promptTextarea as HTMLTextAreaElement).readOnly).toBe(false);
    expect((promptTextarea as HTMLTextAreaElement).value).toBe("Build {{ source_title }}");
    setValue(promptTextarea as HTMLTextAreaElement, "Build updated {{ source_title }}");

    const savePluginButton = buttonByAriaLabelPrefix("保存 ");
    expect(savePluginButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (savePluginButton as HTMLButtonElement).click();
    });
    await flushQueries();

    expect(fetchMock.mock.calls.some(([input, init]) => (
      input.toString().includes("/api/artifact-plugins/terminal/demo_report")
      && init?.method === "PUT"
    ))).toBe(true);

    await waitFor(() => {
      const downloadButton = buttonByAriaLabelPrefix("下载 ");
      expect(downloadButton).toBeInstanceOf(HTMLButtonElement);
      expect((downloadButton as HTMLButtonElement).disabled).toBe(false);
    });

    const deletePluginButton = buttonByAriaLabelPrefix("删除 ");
    expect(deletePluginButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (deletePluginButton as HTMLButtonElement).click();
    });
    await flushQueries();

    expect(document.body.querySelector('[role="alertdialog"]')?.textContent).toContain("删除 artifact plugin demo_report？");
    const confirmDeleteButton = promptButtonByText("删除");
    expect(confirmDeleteButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (confirmDeleteButton as HTMLButtonElement).click();
    });
    await flushQueries();

    expect(fetchMock.mock.calls.some(([input, init]) => (
      input.toString().includes("/api/artifact-plugins/terminal/demo_report")
      && init?.method === "DELETE"
    ))).toBe(true);
  });

  it("takes focus from a focused terminal textarea and closes before terminal Escape handling", () => {
    const terminalTextarea = document.createElement("textarea");
    terminalTextarea.className = "xterm-helper-textarea";
    const terminalEscapeHandler = vi.fn((event: KeyboardEvent) => {
      event.preventDefault();
      event.stopPropagation();
    });
    terminalTextarea.addEventListener("keydown", terminalEscapeHandler);
    document.body.appendChild(terminalTextarea);
    terminalTextarea.focus();

    const onClose = vi.fn();
    renderSettingsModal({ onClose });

    act(() => {
      vi.advanceTimersByTime(16);
    });

    expect(document.activeElement).toBe(container?.querySelector(".settings-modal"));

    act(() => {
      terminalTextarea.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(terminalEscapeHandler).not.toHaveBeenCalled();
  });

  it("closes when Escape is pressed", () => {
    const onClose = vi.fn();
    renderSettingsModal({ onClose });

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("opens theme controls from a nested settings page", () => {
    renderSettingsModal();

    expect(container?.querySelector(".settings-skin-preview-grid")).toBeNull();
    expect(container?.textContent).toContain("界面");

    const themeTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("界面"));
    expect(themeTab).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (themeTab as HTMLButtonElement).click();
    });

    expect(container?.querySelector(".settings-skin-preview-grid")).not.toBeNull();
    expect(container?.textContent).toContain("当前皮肤");
  });

  it("saves the app interface language preference", async () => {
    const onAppLocaleChange = vi.fn();
    renderSettingsModal({ onAppLocaleChange });

    const localeSelect = Array.from(container?.querySelectorAll("select") ?? [])
      .find((select) => select.querySelector("option[value='en-US']"));
    expect(localeSelect).toBeInstanceOf(HTMLSelectElement);

    act(() => {
      (localeSelect as HTMLSelectElement).value = "en-US";
      (localeSelect as HTMLSelectElement).dispatchEvent(new Event("change", { bubbles: true }));
    });

    const saveButton = buttonByAriaLabel("保存");
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);

    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });

    expect(onAppLocaleChange).toHaveBeenCalledWith("en-US");
    expect(window.localStorage.getItem("web-terminal-acp:app-locale")).toBeNull();
  });

});
