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

The packaged app can point at a backend at runtime from **Settings -> Backend URL**.
When no runtime URL is set, Electron defaults to `http://127.0.0.1:8001`.

## Installers

```bash
cd frontend
npm install
# macOS installer (run on macOS for dmg creation, signing, and notarization)
npm run electron:dist:mac
# Windows installer (run on Windows, or Linux with wine/nsis available)
npm run electron:dist:win
```

Artifacts are written to `frontend/release/`.

For CI smoke checks or unsigned prerelease artifacts on Linux:

```bash
cd frontend
npm install
npm run electron:dist:mac:zip
npm run electron:dist:win:portable
```

`electron:dist:mac:zip` produces separate `x64` and `arm64` macOS `.zip` artifacts, with the architecture included in each filename. Use the `arm64` artifact for Apple Silicon Macs; running the `x64` artifact through Rosetta can significantly increase cold-start memory usage. Use the platform-native installer commands above for final signed releases.

Single-architecture macOS zip builds are also available when debugging packaging:

```bash
cd frontend
npm run electron:dist:mac:zip:x64
npm run electron:dist:mac:zip:arm64
```

Packaged builds serve `dist/` on `http://127.0.0.1:4173` so CORS matches localhost origins. The backend allows any `http://127.0.0.1:<port>` origin via `allow_origin_regex`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE` | Optional build-time fallback backend URL; runtime Settings takes precedence |
| `VITE_DEV_SERVER_URL` | Vite URL for `electron:dev` (default `http://127.0.0.1:5173`) |
| `WTA_ELECTRON_STATIC_PORT` | Port for the embedded static server in production (default `4173`) |
| `ELECTRON_DEV` | Force dev mode (load Vite instead of `dist/`) |

## Terminal layout

Electron sets `html.electron-app` and uses `height: 100%` instead of `100dvh`, which avoids incorrect viewport sizing in embedded Chromium. Terminal stages use flex growth (`height: 0; flex: 1`) so the xterm pane fills the workspace.
