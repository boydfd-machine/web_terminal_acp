import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

const LIVE = process.env.WEB_TERMINAL_LIVE_CURSOR_E2E === "1";
const AUTH_KEY = "web-terminal-acp:auth-token";
const CURSOR_OFFICIAL_MODEL_PRESET_ID = "cursor-official";

type Client = { id: string; name: string; status: string; runtime: string };
type WindowOut = {
  id: string;
  cwd: string | null;
  shell_command: string | null;
  remote_session_id: string | null;
  remote_window_id: string | null;
};

test.skip(!LIVE, "Set WEB_TERMINAL_LIVE_CURSOR_E2E=1 to run live Cursor CLI e2e checks.");

function authSecret(): string {
  const envPath = resolve(import.meta.dirname, "../../.env");
  const line = readFileSync(envPath, "utf8").split(/\r?\n/).find((entry) => entry.startsWith("WEB_TERMINAL_AUTH_SECRET="));
  if (!line) throw new Error("WEB_TERMINAL_AUTH_SECRET missing from .env");
  return line.split("=", 2)[1].trim().replace(/^['"]|['"]$/g, "");
}

async function api<T>(request: APIRequestContext, token: string, path: string, options: Parameters<APIRequestContext["fetch"]>[1] = {}) {
  const headers = { Authorization: `Bearer ${token}`, ...(options.headers ?? {}) };
  const response = await request.fetch(path, { ...options, headers });
  expect(response.ok(), `${options.method ?? "GET"} ${path}: ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

async function login(request: APIRequestContext) {
  const response = await request.post("/api/auth/login", { data: { secret: authSecret() } });
  expect(response.ok()).toBeTruthy();
  return (await response.json() as { token: string }).token;
}

async function firstOnlineClient(request: APIRequestContext, token: string) {
  const clients = await api<Client[]>(request, token, "/api/clients");
  const online = clients.find((client) => client.status === "ONLINE");
  expect(online, "an online client is required").toBeTruthy();
  return online as Client;
}

async function createWindow(request: APIRequestContext, token: string, clientId: string, data: Record<string, unknown>) {
  return api<WindowOut>(request, token, `/api/clients/${clientId}/windows`, { method: "POST", data });
}

async function waitForBoundWindow(request: APIRequestContext, token: string, clientId: string, windowId: string) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const window = await api<WindowOut>(request, token, `/api/clients/${clientId}/windows/${windowId}`);
    if (window.remote_session_id && window.remote_window_id) return window;
    await new Promise((resolveTick) => setTimeout(resolveTick, 500));
  }
  throw new Error(`window ${windowId} did not bind a remote tmux id`);
}

async function cleanupWindow(request: APIRequestContext, token: string, clientId: string, windowId: string) {
  const response = await request.delete(`/api/clients/${clientId}/windows/${windowId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect([204, 404]).toContain(response.status());
}

test("cursor official models and launch command include --model", async ({ request }) => {
  const token = await login(request);
  const client = await firstOnlineClient(request, token);
  const suffix = randomUUID().slice(0, 8);
  const projectPath = `/tmp/wt-cursor-e2e-${suffix}`;
  const windows: string[] = [];

  const models = await api<{ models: Array<{ id: string; label: string }> }>(
    request,
    token,
    `/api/clients/${client.id}/agent-clients/cursor/official-models`,
  );
  expect(models.models.length).toBeGreaterThan(0);
  const selectedModel = models.models.find((model) => model.id === "composer-2.5")?.id ?? models.models[0]?.id;
  expect(selectedModel).toBeTruthy();

  try {
    const created = await createWindow(request, token, client.id, {
      cwd: projectPath,
      folder_path: `/E2E/cursor-${suffix}`,
      agent_launch: {
        agent: "cursor",
        command: "agent",
        model_selection: {
          preset_id: CURSOR_OFFICIAL_MODEL_PRESET_ID,
          model: selectedModel,
        },
      },
    });
    windows.push(created.id);
    const bound = await waitForBoundWindow(request, token, client.id, created.id);
    expect(bound.shell_command).toContain("--model");
    expect(bound.shell_command).toContain(String(selectedModel));
  } finally {
    for (const windowId of windows.reverse()) {
      await cleanupWindow(request, token, client.id, windowId);
    }
  }
});
