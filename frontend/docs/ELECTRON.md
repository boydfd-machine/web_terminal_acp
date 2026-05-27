# Electron desktop client

The frontend can be packaged as a desktop app for **Windows** and **macOS**. The app is a **thin client**: it still talks to a running Web Terminal ACP backend (API + WebSocket). It does not embed Postgres, Elasticsearch, or tmux.

## Prerequisites

- Node.js 20+
- Backend reachable from the desktop machine (default dev: `http://127.0.0.1:8001`)

## Development

```bash
cd frontend
npm install
npm run electron:dev
```

This starts Vite on `http://127.0.0.1:5173` and opens Electron against it.

Point the UI at your API when building:

```bash
VITE_API_BASE=http://your-server.example.com:8001 npm run build
```

## Installers

```bash
cd frontend
npm install
# macOS installer (run on macOS for signing/notarization)
npm run electron:dist:mac
# Windows installer (run on Windows, or use CI)
npm run electron:dist:win
```

Artifacts are written to `frontend/release/`.

Packaged builds serve `dist/` on `http://127.0.0.1:4173` so CORS matches localhost origins. The backend allows any `http://127.0.0.1:<port>` origin via `allow_origin_regex`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE` | Backend URL baked into the build (e.g. `http://your-server.example.com:8001`) |
| `VITE_DEV_SERVER_URL` | Vite URL for `electron:dev` (default `http://127.0.0.1:5173`) |
| `WTA_ELECTRON_STATIC_PORT` | Port for the embedded static server in production (default `4173`) |
| `ELECTRON_DEV` | Force dev mode (load Vite instead of `dist/`) |

## Terminal layout

Electron sets `html.electron-app` and uses `height: 100%` instead of `100dvh`, which avoids incorrect viewport sizing in embedded Chromium. Terminal stages use flex growth (`height: 0; flex: 1`) so the xterm pane fills the workspace.
