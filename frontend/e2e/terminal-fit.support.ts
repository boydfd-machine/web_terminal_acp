import { createHash } from "node:crypto";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { Socket } from "node:net";

import { expect, test, type Page } from "@playwright/test";

import type { ClientWindowsActivity, TerminalRecentPage, TreeFolderCore } from "../src/types";

const LOCAL_CLIENT_ID = "00000000-0000-0000-0000-000000000001";
const LOCAL_WINDOW_ID = process.env.PLAYWRIGHT_WINDOW_ID ?? "00000000-0000-0000-0000-000000000002";
const LOCAL_PROJECT_PATH = "/tmp";
const TERMINAL_ACTIVE_VIEW_STORAGE_KEY = "web-terminal-acp:active-terminal-view";
const TERMINAL_SCREENSHOT_PATH = process.env.PLAYWRIGHT_TERMINAL_SCREENSHOT
?? "/tmp/web-terminal-acp-terminal-perfect.png";

type TerminalMetrics = {
hostHeight: number;
renderedHeight: number;
lineCount: number;
terminalRows: number;
stageHeight: number;
workspaceHeight: number;
fillRatio: number;
connectionStatus: string | null;
visibleText: string;
};

async function readTerminalMetrics(page: Page): Promise<TerminalMetrics | null> {
return page.evaluate(() => {
  const host = document.querySelector(".terminal-xterm-host");
  const rows = document.querySelector(".xterm-rows");
  const stage = document.querySelector(".terminal-stage");
  const workspace = document.querySelector(".workspace");
  const status = document.querySelector(".terminal-connection-status");

  if (!(host instanceof HTMLElement) || !(rows instanceof HTMLElement)) {
    return null;
  }

  const lineElements = rows.querySelectorAll("div");
  let renderedHeight = 0;
  if (lineElements.length > 0) {
    const first = lineElements[0].getBoundingClientRect();
    const last = lineElements[lineElements.length - 1].getBoundingClientRect();
    renderedHeight = last.bottom - first.top;
  } else {
    renderedHeight = rows.getBoundingClientRect().height;
  }

  const canvas = document.querySelector(".xterm-screen canvas");
  if (canvas instanceof HTMLElement) {
    const canvasHeight = canvas.getBoundingClientRect().height;
    if (canvasHeight > renderedHeight) {
      renderedHeight = canvasHeight;
    }
  }

  const hostHeight = host.clientHeight;
  const terminalRows = lineElements.length;

  return {
    hostHeight,
    renderedHeight,
    lineCount: terminalRows,
    terminalRows,
    stageHeight: stage instanceof HTMLElement ? stage.clientHeight : 0,
    workspaceHeight: workspace instanceof HTMLElement ? workspace.clientHeight : 0,
    fillRatio: hostHeight > 0 ? renderedHeight / hostHeight : 0,
    connectionStatus: status instanceof HTMLElement ? status.textContent : null,
    visibleText: rows.textContent ?? "",
  };
});
}

async function waitForFilledTerminal(
page: Page,
minRatio = 0.9,
timeoutMs = 60_000,
requiredText?: string,
): Promise<TerminalMetrics> {
const started = Date.now();
let last: TerminalMetrics | null = null;

while (Date.now() - started < timeoutMs) {
  last = await readTerminalMetrics(page);
  if (
    last !== null
    && last.hostHeight > 300
    && last.fillRatio >= minRatio
    && last.renderedHeight > 0
    && last.lineCount >= 20
    && (requiredText === undefined || last.visibleText.includes(requiredText))
  ) {
    return last;
  }
  await page.waitForTimeout(200);
}

throw new Error(
  `Terminal did not fill within ${timeoutMs}ms; last=${JSON.stringify(last)}`,
);
}

function testClient() {
const now = "2026-05-25T13:45:00.000Z";
return {
  id: LOCAL_CLIENT_ID,
  name: "local",
  status: "ONLINE",
  hostname: "playwright",
  install_path: null,
  version: "1.3.5",
  last_update_at: now,
  runtime: "local",
  last_seen_at: now,
  connected_at: now,
  created_at: now,
  updated_at: now,
};
}

function testWindow() {
const now = "2026-05-25T13:45:00.000Z";
return {
  id: LOCAL_WINDOW_ID,
  client_id: LOCAL_CLIENT_ID,
  title: "Playwright Full Screen Terminal",
  folder_id: "00000000-0000-0000-0000-000000000010",
  status: "ACTIVE",
  tmux_session: "playwright",
  tmux_window_id: "@1",
  remote_session_id: null,
  remote_window_id: null,
  cwd: "/tmp",
  shell_command: "/bin/bash",
  summary: null,
  title_tags: ["playwright"],
  runtime_tags: ["bash", LOCAL_PROJECT_PATH, "cwd-/tmp"],
  work_status: {
    state: "RECENT_ACTIVE",
    label: "recent active",
    color: "green",
    last_activity_at: now,
    last_working_activity_at: now,
  },
  title_manually_overridden: false,
  folder_manually_overridden: false,
  command_capture_supported: true,
  summary_job: null,
  created_at: now,
};
}

function testTree() {
const window = testWindow();
return [{
  id: "00000000-0000-0000-0000-000000000010",
  name: "未分类",
  path: "/未分类",
  folders: [],
  windows: [{
    id: window.id,
    title: window.title,
    status: window.status,
    title_tags: window.title_tags,
    created_at: window.created_at,
  }],
}];
}

function terminalOutput(rows = 40): string {
const lines = [
  "\x1b[2J\x1b[H",
  "WEB TERMINAL ACP PLAYWRIGHT FULL SCREEN CHECK",
  "top marker: visible terminal content starts here",
];
for (let index = 1; index <= rows; index += 1) {
  lines.push(`fit-row-${String(index).padStart(2, "0")} ` + "#".repeat(56));
}
lines.push("bottom marker: visible terminal content reaches the lower viewport");
return `${lines.join("\r\n")}\r\n`;
}

type MockApiOptions = {
slowTreeMs?: number;
slowSocketMs?: number;
tree?: TreeFolderCore[];
activity?: ClientWindowsActivity;
recents?: TerminalRecentPage;
onRequest?: (url: URL) => void;
onTerminalMessage?: (message: string | Buffer, ws: MockTerminalSocket) => void;
afterTerminalConnected?: (ws: MockTerminalSocket) => void;
};

type MockTerminalSocket = {
send: (message: string | Buffer) => void;
};

const closeMockServers: Array<() => Promise<void>> = [];

function corsHeaders() {
return {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
};
}

function websocketAcceptKey(key: string): string {
return createHash("sha1")
  .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
  .digest("base64");
}

function encodeWsFrame(message: string | Buffer): Buffer {
const payload = Buffer.isBuffer(message) ? message : Buffer.from(message);
const opcode = Buffer.isBuffer(message) ? 0x2 : 0x1;
if (payload.length < 126) {
  return Buffer.concat([Buffer.from([0x80 | opcode, payload.length]), payload]);
}
if (payload.length < 65536) {
  const header = Buffer.alloc(4);
  header[0] = 0x80 | opcode;
  header[1] = 126;
  header.writeUInt16BE(payload.length, 2);
  return Buffer.concat([header, payload]);
}
const header = Buffer.alloc(10);
header[0] = 0x80 | opcode;
header[1] = 127;
header.writeBigUInt64BE(BigInt(payload.length), 2);
return Buffer.concat([header, payload]);
}

function decodeWsFrames(buffer: Buffer): { messages: Array<string | Buffer>; remaining: Buffer; closed: boolean } {
const messages: Array<string | Buffer> = [];
let offset = 0;
let closed = false;

while (buffer.length - offset >= 2) {
  const first = buffer[offset];
  const second = buffer[offset + 1];
  const opcode = first & 0x0f;
  const masked = (second & 0x80) !== 0;
  let length = second & 0x7f;
  let headerLength = 2;
  if (length === 126) {
    if (buffer.length - offset < 4) break;
    length = buffer.readUInt16BE(offset + 2);
    headerLength = 4;
  } else if (length === 127) {
    if (buffer.length - offset < 10) break;
    length = Number(buffer.readBigUInt64BE(offset + 2));
    headerLength = 10;
  }

  const maskLength = masked ? 4 : 0;
  const frameLength = headerLength + maskLength + length;
  if (buffer.length - offset < frameLength) break;
  const mask = masked ? buffer.subarray(offset + headerLength, offset + headerLength + 4) : null;
  const payload = Buffer.from(buffer.subarray(offset + headerLength + maskLength, offset + frameLength));
  if (mask !== null) {
    for (let index = 0; index < payload.length; index += 1) {
      payload[index] ^= mask[index % 4];
    }
  }
  if (opcode === 0x8) {
    closed = true;
    offset += frameLength;
    break;
  }
  if (opcode === 0x1) {
    messages.push(payload.toString("utf8"));
  } else if (opcode === 0x2) {
    messages.push(payload);
  }
  offset += frameLength;
}

return { messages, remaining: buffer.subarray(offset), closed };
}

async function startMockApiServer(options?: MockApiOptions): Promise<{ baseUrl: string; close: () => Promise<void> }> {
const window = testWindow();
const clientPath = `/api/clients/${LOCAL_CLIENT_ID}`;
const windowPath = `${clientPath}/windows/${LOCAL_WINDOW_ID}`;
const sockets = new Set<Socket>();

const sendJson = (response: ServerResponse, payload: unknown) => {
  response.writeHead(200, {
    ...corsHeaders(),
    "Content-Type": "application/json",
  });
  response.end(JSON.stringify(payload));
};

const server: Server = createServer((request, response) => {
  void (async () => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    options?.onRequest?.(url);
    if (request.method === "OPTIONS") {
      response.writeHead(204, corsHeaders());
      response.end();
      return;
    }
    if (url.pathname === "/api/auth/status") {
      sendJson(response, { enabled: false });
    } else if (url.pathname === "/api/clients") {
      sendJson(response, [testClient()]);
    } else if (url.pathname === `${clientPath}/terminal-projects`) {
      sendJson(response, [{ project_path: LOCAL_PROJECT_PATH, window_count: 1 }]);
    } else if (url.pathname === `${clientPath}/projects`) {
      sendJson(response, [{
        client_id: LOCAL_CLIENT_ID,
        path: LOCAL_PROJECT_PATH,
        display_name: null,
        summary_status: null,
        summary_updated_at: null,
        window_count: 1,
      }]);
    } else if (url.pathname === `${clientPath}/tree`) {
      if (options?.slowTreeMs) {
        await new Promise((resolve) => setTimeout(resolve, options.slowTreeMs));
      }
      sendJson(response, options?.tree ?? testTree());
    } else if (url.pathname === `${clientPath}/windows/activity`) {
      sendJson(response, options?.activity ?? {
        windows: [{
          window_id: LOCAL_WINDOW_ID,
          work_status: window.work_status,
          runtime_tags: window.runtime_tags,
          last_agent_task_completed_at: null,
          git_worktree: null,
        }],
      });
    } else if (url.pathname === windowPath) {
      sendJson(response, window);
    } else if (url.pathname === `${clientPath}/project-summaries`) {
      sendJson(response, []);
    } else if (url.pathname === `${clientPath}/terminal-recents` && request.method === "GET") {
      sendJson(response, options?.recents ?? {
        items: [{ window_id: LOCAL_WINDOW_ID, title: window.title, last_used_at: window.created_at }],
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: Number(url.searchParams.get("page_size") ?? "20"),
        total: 1,
        total_pages: 1,
      });
    } else if (url.pathname === `${clientPath}/terminal-recents` && request.method === "POST") {
      sendJson(response, { window_id: LOCAL_WINDOW_ID, title: window.title, last_used_at: window.created_at });
    } else if (url.pathname === `${clientPath}/search`) {
      sendJson(response, { query: "", results: [] });
    } else {
      response.writeHead(404, corsHeaders());
      response.end();
    }
  })().catch(() => {
    response.writeHead(500, corsHeaders());
    response.end();
  });
});

server.on("connection", (socket) => {
  sockets.add(socket);
  socket.on("close", () => sockets.delete(socket));
});

server.on("upgrade", (request: IncomingMessage, socket: Socket) => {
  const url = new URL(request.url ?? "/", "http://127.0.0.1");
  if (url.pathname !== `${clientPath}/terminal/${LOCAL_WINDOW_ID}`) {
    socket.destroy();
    return;
  }

  const key = request.headers["sec-websocket-key"];
  if (typeof key !== "string") {
    socket.destroy();
    return;
  }
  socket.write([
    "HTTP/1.1 101 Switching Protocols",
    "Upgrade: websocket",
    "Connection: Upgrade",
    `Sec-WebSocket-Accept: ${websocketAcceptKey(key)}`,
    "\r\n",
  ].join("\r\n"));

  const ws: MockTerminalSocket = {
    send: (message) => socket.write(encodeWsFrame(message)),
  };
  let incoming = Buffer.alloc(0);
  socket.on("data", (chunk) => {
    incoming = Buffer.concat([incoming, chunk]);
    const decoded = decodeWsFrames(incoming);
    incoming = decoded.remaining;
    if (decoded.closed) {
      socket.end();
      return;
    }
    for (const message of decoded.messages) {
      options?.onTerminalMessage?.(message, ws);
      if (typeof message !== "string") {
        continue;
      }
      try {
        const parsed = JSON.parse(message) as { type?: unknown };
        if (parsed.type === "resize") {
          ws.send(terminalOutput());
        }
      } catch {
        continue;
      }
    }
  });
  setTimeout(() => {
    ws.send(JSON.stringify({ type: "terminal_status", status: "connected" }));
    ws.send(terminalOutput());
    options?.afterTerminalConnected?.(ws);
  }, options?.slowSocketMs ?? 25);
});

await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();
if (address === null || typeof address === "string") {
  throw new Error("mock API server did not bind to a TCP port");
}
return {
  baseUrl: `http://127.0.0.1:${address.port}`,
  close: () => new Promise<void>((resolve) => {
    for (const socket of sockets) {
      socket.destroy();
    }
    server.close(() => resolve());
  }),
};
}

async function mockApi(page: Page, options?: MockApiOptions) {
const server = await startMockApiServer(options);
closeMockServers.push(server.close);
await page.addInitScript((apiBase) => {
  (window as Window & { __WEB_TERMINAL_API_BASE?: string }).__WEB_TERMINAL_API_BASE = apiBase;
}, server.baseUrl);
}

function terminalPath(): string {
return `/clients/${encodeURIComponent(LOCAL_CLIENT_ID)}/terminals/${encodeURIComponent(LOCAL_WINDOW_ID)}`;
}

test.afterEach(async () => {
  const cleanup = closeMockServers.splice(0);
  await Promise.all(cleanup.map((close) => close()));
});


export {
  expect,
  test,
  readTerminalMetrics,
  waitForFilledTerminal,
  testClient,
  testWindow,
  testTree,
  terminalOutput,
  mockApi,
  terminalPath,
  TERMINAL_SCREENSHOT_PATH,
  LOCAL_CLIENT_ID,
  LOCAL_WINDOW_ID,
  TERMINAL_ACTIVE_VIEW_STORAGE_KEY
};
export type { TerminalMetrics, MockApiOptions, MockTerminalSocket };
