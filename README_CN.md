[English](README.md)

# Web Terminal ACP

面向 **「以产物为中心的 Agent 终端」** 的 Web 控制台：在浏览器里跑 shell 与 AI 编程 Agent，用虚拟目录树整理会话，接入 Claude / Codex / Cursor 活动流，并用 Elasticsearch 做全文检索。

适合需要 **长期留存终端与 Agent 工作记录**、又不想放弃本机 tmux、Claude Code、Codex、Cursor CLI 的场景。

## 功能概览

- **浏览器终端** — `xterm.js` + FastAPI WebSocket，底层由 tmux 承载
- **虚拟目录树** — 按项目分组、支持自动建议路径与手动拖拽
- **多客户端** — 服务端本地运行时 + 可选 **远程 client-agent**（SSH 一键安装）
- **AI 会话采集** — Claude JSONL、Codex trace、Cursor CLI 适配器
- **摘要与搜索** — OpenAI 兼容 LLM 生成标题/标签/摘要；ES 索引终端输出与事件
- **Git worktree** — Agent 在独立 worktree 中改代码（见 `.cursor/skills/web-terminal-git-worktree`）
- **工作状态** — 忙碌/空闲、桌面通知、最近终端、项目级摘要

MVP **不包含** 内置登录：默认只监听本机，对外请用 Nginx 等反向代理并自行做鉴权。

## 架构

| 组件 | 作用 |
|------|------|
| React 前端 | 目录树、终端、搜索、远程客户端引导 |
| FastAPI | REST、WebSocket、tmux、采集、摘要任务 |
| PostgreSQL | 目录、虚拟窗口、客户端、AI 会话、事件 |
| Elasticsearch | 终端块、AI 事件、摘要的检索 |
| tmux | Shell 与 Agent 进程宿主 |
| client-agent | 可选远程守护进程 |

详细设计见 [docs/DESIGN.md](docs/DESIGN.md)。

## 环境要求

- Docker 与 Docker Compose
- 在宿主机直接跑后端时需要 **tmux**（镜像内已带）
- 摘要功能：任意 **OpenAI 兼容** HTTP API（Ollama、vLLM、云厂商等）
- 可选：已安装并配置 Claude Code / Codex / Cursor CLI

**Linux + Elasticsearch：** 若 ES 容器起不来，请提高 `vm.max_map_count`（例如 `sudo sysctl -w vm.max_map_count=262144`）。`make` 会在数值过低时提示。

## 快速开始（Docker Compose）

```bash
git clone https://github.com/<your-org>/web_terminal_acp.git
cd web_terminal_acp
cp .env.example .env
# 编辑 .env — 至少配置路径；需要摘要时配置 OPENAI_COMPAT_*
```

首次需构建较重的 backend 基础镜像（含 Node、Claude Code、Codex、acpx、Chromium）：

```bash
docker compose --profile build-base build backend-base
docker compose build
docker compose up -d --wait
```

- 前端 UI：**http://localhost:5173**
- 后端健康检查：**http://localhost:8001/healthz**（默认映射端口）

使用 Makefile 时，数据可落在项目下的 `./data`：

```bash
make preflight/init
make deploy-up
```

## 配置说明

将 `.env.example` 复制为 `.env`。常用项：

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL（async） | Compose 内 Postgres |
| `ELASTICSEARCH_URL` | ES 地址 | `http://127.0.0.1:19201` |
| `CLAUDE_PROJECTS_DIR` | Claude 工程目录（JSONL） | `~/.claude/projects` |
| `WORKSPACE_DIR` | 挂载到容器 `/workspace` 的宿主机路径 | `~/workspace` |
| `OPENAI_COMPAT_*` | 摘要 LLM | 见 `.env.example` |
| `BACKEND_PUBLISHED_PORT` | API 对外端口 | `8001` |

默认会把 `~/.claude`、`~/.codex` 等挂进容器，便于 Agent 使用本机凭据——请按安全需求自行收紧。

**切勿** 将 `.env` 提交到 Git；对外暴露端口前请改强数据库密码并加反向代理鉴权。

## 本地开发

```bash
make services-up
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

cd frontend && npm install && npm run dev -- --host 127.0.0.1
```

测试：

```bash
make backend-test
```

## 远程客户端

1. 启动控制面（Compose 或本地后端）。
2. 打开 UI → **Clients** → **Bootstrap remote client**。
3. 填写 SSH、私钥、安装路径、服务器 URL。
4. 服务端在远程机安装 `~/.web-terminal-acp/config.json` 并拉起 `client-agent`。

远程机需要 tmux、能跑 client-agent 的 Python，以及到 Web Terminal API 的网络连通。

## Agent 与 Git worktree

在已设置 `WEB_TERMINAL_WINDOW_ID` 的 Web Terminal 里，Agent 应遵循：

`.cursor/skills/web-terminal-git-worktree`

会在 `.web-terminal-acp/worktrees/<window-id>` 创建 worktree 并注册到 UI，避免直接在主 checkout 改代码。

## 许可证

MIT — 见 [LICENSE](LICENSE)。
