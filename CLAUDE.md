# CLAUDE.md

## Client Versioning

- Any client-side change must include a version bump in the same change set.
- Use Semantic Versioning (`MAJOR.MINOR.PATCH`) as the default convention.
- Increment `MAJOR` for incompatible protocol, API, storage, or deployment changes that require coordinated upgrades.
- Increment `MINOR` for backward-compatible client features or behavior additions.
- Increment `PATCH` for backward-compatible bug fixes, small UI adjustments, refactors, or internal-only client changes.
- Keep all project version sources that represent the client in sync, such as `backend/app/version.py` and `frontend/package.json` when applicable.
- To reduce routine agent merge conflicts, run `scripts/install-version-merge-driver.sh` once per clone. The repo marks version files with `merge=web-terminal-version`; the local driver keeps equal versions unchanged and resolves version-only conflicts to the highest SemVer across `backend/app/version.py`, `frontend/package.json`, and `frontend/package-lock.json`.

## Web Terminal Agent 开发

在 Web Terminal 中开发时，必须使用系统 skill **`web-terminal-git-worktree`**（见 [AGENTS.md](./AGENTS.md)）。任务完成后把 `agent/<suffix>` 合并回 `main` 时，必须使用 `merge-agent-branch` skill / `python3 scripts/merge-agent-branch.py` 通过仓库级 merge 锁完成，不要在主仓库 checkout 手工 `git merge agent/<suffix>`。

## Code Structure

- Keep source code files at or below 500 lines. Split long files by cohesive components, hooks, services, or immutable value objects before adding more behavior.
- Delete obsolete code instead of commenting it out. Do not comment code whose meaning is already clear.
- Add or preserve tests before refactoring behavior whenever practical. Frontend logic needs focused tests around extracted logic, and backend refactors should move logic toward immutable, side-effect-free objects.

## Local Testing

- Run backend pytest locally with 8-way xdist concurrency by default.
- Unit tests: `cd backend && uv run pytest tests/unit -n 8 -q`.
- Integration tests: `cd backend && uv run pytest tests/integration -n 8 -q`.
- Full backend validation: `cd backend && uv run pytest tests -n 8 -q`.
- If a test must be run serially to debug ordering, isolation, or xdist-specific behavior, document that reason in the validation notes.

## Frontend Design

- Prefer icon-only controls for generic, unambiguous actions such as close, save, delete, download, edit, refresh, expand/collapse, pagination, and settings. Give every icon-only button a clear `aria-label` and `title`; keep text buttons when the label is the domain action or primary workflow command.

## Backend Context Structure

- Backend business code is organized by vertical context under `backend/app/contexts/`, not by the legacy horizontal `routers/`, `services/`, `repositories/`, `schemas/`, or `domain/` directories.
- Current contexts and owned logic:
  - `windows`: window creation, cloning, deletion, folder assignment, launch plans, runtime start orchestration, title/command history, response projections, agent record views, and window detail routes.
  - `clients`: local/remote client CRUD, listing, registration keys, direct registration, bootstrap SSH/installer packaging, client update jobs, client-agent websocket routes, connection registry, and runner helpers.
  - `agent_profiles`: reusable Web Terminal agent profiles, agent-client capabilities, profile manifests, agent config projection, profile store, and agent-client config store.
  - `terminal_runtime`: terminal websocket and selection routes, aux terminal routes, tmux/local/remote runtime, PTY control, terminal broker, output recorder, command markers, runtime binding, git worktree tracking, offline monitor, and tmux paths/targets.
  - `terminal_artifacts`: artifact API routes, artifact schemas/domain objects, generation scheduling, terminal execution, artifact repository, and interrupted artifact reconciliation.
  - `workspace`: folders, projects, project files, project todos, project summaries, summarizer, summary scheduler/worker, folder splitting, folder access, browse roots, and their repositories.
  - `activity`: trace ingest, AI session/event projection, agent work presence, terminal work status, terminal notifications, terminal recents, window activity, runtime tags, and activity repositories.
- Layer rules inside each context:
  - `api/` owns FastAPI routes, request/response schemas, dependency wiring, HTTP error mapping, and API-specific projection. It delegates behavior to `application/`.
  - `application/` owns use cases, orchestration, policies, projections, background jobs, and cross-context calls. It may depend on its own `domain/` and `infrastructure/`, plus other contexts' `application/` or public API DTOs.
  - `domain/` owns pure value objects, enums, protocol types, validation concepts, and side-effect-free rules. It must not import `api/`, `application/`, database/session code, or FastAPI.
  - `infrastructure/` owns persistence, database queries, tmux/PTY/remote-client adapters, filesystem stores, subprocess runners, and other external-system adapters.
- Cross-context boundaries:
  - Do not import another context's `infrastructure/` repository or adapter directly. Call that context's `application/` service or public DTO/projection instead.
  - Keep context modules importing canonical context/platform/shared paths, not legacy facade paths.
  - Avoid loading one implementation through both old and new module names. Legacy imports that must remain compatible should install explicit `sys.modules` aliases so monkeypatches, singletons, routers, and caches hit the same module object.
- Platform/shared code:
  - `backend/app/platform/` holds cross-cutting platform capabilities: auth routes/schemas, cache backends, polling response cache, search routes/index/schemas, UI events/routes, UI settings routes/repository/schemas, ingest normalizers/watchers, and plugin registries for agent tools, agent plugins, and artifact plugins.
  - `backend/app/shared/` holds small shared helpers such as LLM JSON parsing and redaction.
  - Do not create business contexts for `auth`, `db`, `config`, cache, search infrastructure, UI event hub, redaction, LLM JSON, or plugin registries.
- Legacy horizontal paths are compatibility facades only:
  - `backend/app/routers/**`, `backend/app/services/**`, `backend/app/repositories/**`, `backend/app/domain/**`, `backend/app/schemas/**`, `backend/app/agent_tools/**`, `backend/app/agent_plugins/**`, and `backend/app/artifact_plugins/**` must not receive new behavior.
  - Add new behavior to the owning `contexts/**`, `platform/**`, or `shared/**` canonical module, then keep legacy imports pointing at that module when compatibility matters.
- Tests for new behavior should import the concrete canonical module directly. Add focused compatibility tests when preserving old import paths matters.

## Project Skills

- `web-terminal-git-worktree` 是系统内置 skill，不再维护在 `.codex/skills`、`.claude/skills`、`.cursor/skills` 中。
- 项目级 skill 必须同时维护 Claude Code、Codex、Cursor 三份：`.claude/skills/<name>`、`.codex/skills/<name>`、`.cursor/skills/<name>`。
- 新增或修改项目 skill 时，三份 `SKILL.md`、脚本和必要 metadata 必须保持行为一致；不要只更新其中一个 agent 的版本。
- Android app 打包使用 `android-app-release` skill；常用入口是 `make android-release`、`make android-local-release`、`make android-debug`。

## Remote Client Bundle

- Remote client bootstrap/self-update 只上传 `backend/app/contexts/clients/infrastructure/bootstrap_installer.py::client_app_file_contents()` 中列出的精简包，不会自动包含整个 backend；`backend/app/services/bootstrap/installer.py` 只是兼容 facade。
- `backend/app/client_agent/**` 新增任何启动或运行时 `app.*` import 时，同步更新精简包清单，尤其是 canonical `app.contexts.*`、`app.platform.*`、`app.shared.*` 模块，以及仍需兼容的 legacy facade；remote client 在 WebSocket hello 前退出时，优先查远端 `~/.web-terminal-acp/logs/client.stdout.log`（stdout/stderr 捕获）和 `~/.web-terminal-acp/logs/client.log`（带时间戳的滚动 Python logger 输出）的 `ImportError` / `ModuleNotFoundError`。
- 包清单变更必须有隔离包导入测试覆盖，例如确认精简包可单独 import `app.client_agent.runner`。
- 已离线且启动不起来的 remote client 无法 self-update，需要重新 Bootstrap remote client。

## Web Terminal 性能优先级

Web Terminal 的性能优化和回归判断必须按以下优先级排序：

1. 用户针对 terminal 的输入输出显示是最高优先级。用户输入必须瞬间反应，屏幕显示也必须瞬间反应；这是最终最核心的体验部分，必须有足够的自动化测试和回归覆盖。
2. 各种状态展示是第二优先级。
3. Agent record 和命令历史是第三优先级。
4. Git worktree 状态是第四优先级。

当这些目标发生冲突时，优先保护第一优先级的 terminal 输入、输出和屏幕显示延迟，不允许为了状态、agent record、命令历史或 git worktree 状态牺牲第一优先级体验。
