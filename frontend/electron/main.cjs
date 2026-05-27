const { app, BrowserWindow, shell } = require("electron");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL ?? "http://127.0.0.1:5173";
const STATIC_HOST = process.env.WTA_ELECTRON_STATIC_HOST ?? "127.0.0.1";
const STATIC_PORT = Number(process.env.WTA_ELECTRON_STATIC_PORT ?? "4173");

/** @type {import("node:http").Server | null} */
let staticServer = null;

function isDevMode() {
  return !app.isPackaged || process.env.ELECTRON_DEV === "1";
}

function contentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".json":
      return "application/json; charset=utf-8";
    case ".svg":
      return "image/svg+xml";
    case ".png":
      return "image/png";
    case ".ico":
      return "image/x-icon";
    case ".woff2":
      return "font/woff2";
    default:
      return "application/octet-stream";
  }
}

function startStaticServer(distDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((request, response) => {
      const requestUrl = new URL(request.url ?? "/", `http://${STATIC_HOST}`);
      let relativePath = decodeURIComponent(requestUrl.pathname);
      if (relativePath === "/") {
        relativePath = "/index.html";
      }

      const filePath = path.join(distDir, relativePath);
      if (!filePath.startsWith(distDir)) {
        response.writeHead(403);
        response.end("Forbidden");
        return;
      }

      fs.readFile(filePath, (error, data) => {
        if (error) {
          const fallback = path.join(distDir, "index.html");
          fs.readFile(fallback, (fallbackError, fallbackData) => {
            if (fallbackError) {
              response.writeHead(404);
              response.end("Not found");
              return;
            }
            response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            response.end(fallbackData);
          });
          return;
        }

        response.writeHead(200, { "Content-Type": contentType(filePath) });
        response.end(data);
      });
    });

    server.on("error", reject);
    server.listen(STATIC_PORT, STATIC_HOST, () => {
      staticServer = server;
      resolve(`http://${STATIC_HOST}:${STATIC_PORT}/`);
    });
  });
}

async function resolveAppUrl() {
  if (isDevMode()) {
    return DEV_SERVER_URL;
  }

  const distDir = path.join(__dirname, "..", "dist");
  return startStaticServer(distDir);
}

function notifyRendererResize(win) {
  win.webContents.executeJavaScript(
    "window.dispatchEvent(new Event('resize'));",
    true,
  ).catch(() => {
    // Renderer may still be loading.
  });
}

async function createMainWindow() {
  const appUrl = await resolveAppUrl();
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.once("ready-to-show", () => {
    win.show();
    notifyRendererResize(win);
  });

  win.on("resize", () => {
    notifyRendererResize(win);
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  await win.loadURL(appUrl);
  return win;
}

app.whenReady().then(() => {
  void createMainWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("will-quit", () => {
  if (staticServer !== null) {
    staticServer.close();
    staticServer = null;
  }
});
