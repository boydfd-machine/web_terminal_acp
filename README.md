[中文](README_CN.md)

# Web Terminal ACP

A web-based control plane for **artifact-centric agent terminals**: run shells and AI coding agents in the browser, organize sessions in a virtual folder tree, ingest Claude/Codex/Cursor activity, and search everything with Elasticsearch-backed full-text search.

Built for operators who want a durable record of terminal work—not just a live PTY—without giving up tmux, Claude Code, Codex, or Cursor CLI on the host.

## What you get

- **Browser terminals** — `xterm.js` + FastAPI WebSocket bridge into tmux-backed shells
- **Virtual folder tree** — group terminals by project, auto-suggested paths, manual moves
- **Multi-client** — local runtime on the server plus optional **remote clients** over WebSocket (SSH bootstrap installs the agent on another machine)
- **AI session ingest** — Claude Code JSONL watcher, Codex trace receiver, Cursor CLI adapter registry
- **Summaries & search** — OpenAI-compatible LLM for titles/tags/summaries; Elasticsearch for terminal output and events
- **Git worktree tracking** — OSC markers + UI for agent-linked worktrees (see `.cursor/skills/web-terminal-git-worktree`)
- **Agent presence** — working/idle badges, desktop notifications, recent terminals, project-level summaries

Authentication is **not** built into the MVP: bind locally and put Nginx (or another reverse proxy) in front for LAN/WAN access.

## Architecture

| Layer | Role |
|-------|------|
| **React UI** | Folder tree, terminal panes, search, client bootstrap, settings |
| **FastAPI** | REST, WebSockets, tmux orchestration, ingest, summary workers |
| **PostgreSQL** | Folders, virtual windows, clients, AI sessions, events, jobs |
| **Elasticsearch** | Search index for terminal chunks, AI events, summaries |
| **tmux** | Process host for shells and agent CLIs |
| **client-agent** | Optional remote daemon (`python -m app.client_agent`) |

See [docs/DESIGN.md](docs/DESIGN.md) for the full product design.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- **tmux** on the host when running the backend outside Docker (Compose backend image includes tmux)
- For summaries: any **OpenAI-compatible** HTTP API (Ollama, vLLM, cloud provider, etc.)
- Optional: Claude Code / Codex / Cursor CLI installed and configured on the machine whose sessions you want to ingest

**Elasticsearch on Linux:** if the ES container fails to start, raise `vm.max_map_count` (e.g. `sudo sysctl -w vm.max_map_count=262144`). The Makefile prints a warning when it is too low.

## Quick start (Docker Compose)

```bash
git clone https://github.com/<your-org>/web_terminal_acp.git
cd web_terminal_acp
cp .env.example .env
# Edit .env — at minimum set paths and OPENAI_COMPAT_* if you want summaries
```

Build the heavy backend base image once (includes Node, Claude Code, Codex, acpx, Chromium for agent-browser):

```bash
docker compose --profile build-base build backend-base
docker compose build
docker compose up -d --wait
```

Open the UI at **http://localhost:5173** (frontend). API health: **http://localhost:8001/healthz** (default published backend port).

### First-time data directories

Compose uses named volumes for Postgres and Elasticsearch. For bind mounts under `./data` instead, use the Makefile:

```bash
make preflight/init   # creates ./data/postgres and ./data/elasticsearch
make deploy-up
```

## Configuration

Copy `.env.example` to `.env`. Important variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async PostgreSQL URL | local Compose Postgres |
| `ELASTICSEARCH_URL` | Elasticsearch base URL | `http://127.0.0.1:19201` |
| `CLAUDE_PROJECTS_DIR` | Claude Code projects root (JSONL ingest) | `~/.claude/projects` |
| `WORKSPACE_DIR` | Host path mounted into backend as `/workspace` | `~/workspace` |
| `OPENAI_COMPAT_BASE_URL` | Summarization API base | `http://127.0.0.1:11434/v1` |
| `OPENAI_COMPAT_API_KEY` | API key for summarizer | `dev-local-key` |
| `OPENAI_COMPAT_MODEL` | Model name | `local-summarizer` |
| `BACKEND_PUBLISHED_PORT` | Host port for API | `8001` |
| `VITE_API_BASE` | Frontend build-time API origin; leave empty for Docker nginx proxying, set `http://127.0.0.1:8000` for local Vite development | empty |

Agent tool configs are mounted from `~/.claude`, `~/.codex`, `~/.agents`, `~/.acpx` by default so in-container agents share your host credentials (adjust for your threat model).

**Security:** never commit `.env`. Use strong Postgres passwords and proxy auth before exposing ports on a network.

## Local development (without full Docker app stack)

```bash
# Terminal 1 — infra only
make services-up

# Terminal 2 — backend
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 3 — frontend
cd frontend && npm install && npm run dev -- --host 127.0.0.1
```

Run tests:

```bash
make backend-test
make frontend-build   # tsc + vite build
```

## Remote client bootstrap

1. Start the control plane (Compose or local backend).
2. In the UI, open **Clients** → **Bootstrap remote client**.
3. Provide SSH host/user/port, private key (and passphrase if needed), install path, and server URL.
4. The server installs `~/.web-terminal-acp/config.json` and starts `client-agent` on the remote host over WebSocket.

Remote machines need tmux, a Python runtime with venv/ensurepip support (for example `python3-venv` on Debian/Ubuntu), and network access back to your Web Terminal API. To run Codex or Claude Code from remote terminals, install those CLIs on the remote host in `PATH`; `~/.web-terminal-acp/npm-global/bin` is added automatically for user-local npm installs.

## Agent git worktrees (Cursor / Claude / Codex)

When `WEB_TERMINAL_WINDOW_ID` is set in a managed terminal, agents should use the bundled skill:

`.cursor/skills/web-terminal-git-worktree`

It creates `.web-terminal-acp/worktrees/<window-id>`, registers the worktree with the UI, and keeps edits off the main checkout.

## Project layout

```
web_terminal_acp/
├── backend/          # FastAPI, client-agent, migrations, tests
├── frontend/         # React + Vite + xterm.js
├── docs/DESIGN.md    # Product & data model design
├── docker-compose.yml
├── Makefile
└── scripts/build-images.sh
```

## Versioning

Client protocol and UI version are kept in sync:

- `backend/app/version.py`
- `frontend/package.json`

Bump **PATCH** for fixes, **MINOR** for compatible features, **MAJOR** for breaking protocol or storage changes.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. For development workflow notes aimed at coding agents, see [AGENTS.md](AGENTS.md).
