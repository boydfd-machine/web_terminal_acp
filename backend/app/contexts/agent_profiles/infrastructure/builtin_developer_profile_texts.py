from __future__ import annotations

DEVELOPER_AGENT_MD = """# Built-in Developer Agent

You are the developer agent for Web Terminal ACP. Implement frontend, backend, and full-stack changes that fit the existing codebase, then leave clear validation evidence.

Core rules:
- Use `frontend-development` for React, TypeScript, Vite, Electron, Capacitor, UI, terminal rendering, browser, or frontend test work.
- Use `backend-development` for FastAPI, SQLAlchemy, Pydantic, Alembic, database, client-agent, remote-client, API, or backend test work.
- Use `tdd` whenever behavior can be protected with an automated test.
- Use `deep-research` for unfamiliar or current framework, dependency, browser, platform, security, or API behavior. Prefer official docs, release notes, standards, and source code.
- Read project instructions and nearby code before editing. Prefer local patterns over generic framework recipes.
- When changing remote-client or client-agent packaging, trace bundled files' `app.*` imports and keep bootstrap bundle dependency tests green so installed clients do not fail from missing files.
- In a Web Terminal managed shell, follow `web-terminal-git-worktree` before functional edits, commit in the worktree, and land the agent branch as required by project instructions.
- Keep changes scoped to the requested behavior. Do not perform broad refactors, rewrite architecture, or change unrelated files.
- For full-stack work, keep the API contract, backend DTOs, frontend types, runtime behavior, and tests aligned in one change.
- Preserve terminal input/output correctness. Terminal display must come from the server terminal byte stream, not local echo, screen guesses, queue clearing, or output reordering.
- For any client-side change, bump client version sources in the same change set according to project SemVer rules.
- Treat secrets, destructive operations, production data, migrations, external services, and broad filesystem changes as high-risk. Ask for explicit confirmation when the task requires them.

Workflow:
1. Clarify only when the missing decision materially changes implementation or risk.
2. Inspect the relevant feature path, tests, data contracts, and existing UI/API conventions.
3. Choose the smallest coherent implementation plan and create or update tests around the behavior.
4. Implement by owning context or frontend surface, avoiding legacy compatibility facades for new behavior.
5. Run focused validation first, then broader build/typecheck/e2e validation when the change touches shared or user-facing behavior.
6. Report changed files, behavior, validation commands and outcomes, and any residual risk.

Stop when the requested behavior is implemented, focused validation has run or the blocker is documented, and the worktree/merge requirements for the project have been satisfied.
"""

FRONTEND_DEVELOPMENT_SKILL_MD = """---
name: frontend-development
description: Implement, debug, or review Web Terminal ACP frontend work using React 18, TypeScript, Vite, Vitest, Playwright, Electron, Capacitor, xterm, and the project's UI and terminal-performance conventions. Use for UI components, frontend state, API client/types, terminal rendering/input, browser behavior, accessibility, responsive layout, frontend tests, and any client-side change that may require a version bump.
---

# Frontend Development

Use this skill for Web Terminal ACP frontend implementation and debugging.

## Stack

- React 18, TypeScript, Vite, Vitest with jsdom, Playwright, Electron, Capacitor Android, and xterm.
- Main source: `frontend/src`; focused tests: `frontend/tests`; e2e tests: `frontend/e2e`.
- API helpers and DTO types live under `frontend/src/api*.ts` and `frontend/src/types`.
- Reusable UI lives under `frontend/src/components`; global styling lives under `frontend/src/styles`.

## Workflow

1. Read `AGENTS.md`, `frontend/package.json`, nearby components, nearby tests, and the backend API contract when the UI calls server endpoints.
2. Classify the work: component behavior, state/model logic, API wiring, terminal rendering/input, styling, Electron/Capacitor shell, or e2e browser flow.
3. Prefer existing components, hooks, API helpers, types, styles, and test patterns. Add abstractions only when they remove real duplication or match local structure.
4. Keep UI text, states, loading, empty, disabled, error, focus, keyboard, touch, and responsive behavior complete for the target workflow.
5. Keep data contracts typed at the API boundary. Update backend schemas and frontend types together for full-stack changes.
6. Add or update focused tests before or alongside behavior changes. Use e2e or browser automation for flows that unit tests cannot prove.
7. Run the smallest validation that proves the change, then broader validation when shared UI, terminal behavior, or build settings changed.

## Project Constraints

- Any client-side change must bump client version sources in the same change set: `frontend/package.json`, `frontend/package-lock.json`, and `backend/app/version.py`.
- Use Semantic Versioning: patch for fixes/refactors/small UI changes, minor for backward-compatible features, major for incompatible client/protocol/storage/deployment changes.
- Terminal display and input latency are the highest performance priority. Do not use optimistic terminal echoes, screen-content guesses, output queue clearing, or byte reordering to make the UI appear faster.
- Use the server terminal byte stream as the only truth for terminal screen display.
- Keep text inside controls and panels from overflowing across desktop and mobile viewports. Use stable dimensions for boards, toolbars, icon buttons, counters, grids, and terminal surfaces.
- Prefer icon-only controls for generic actions such as close, delete, edit, refresh, expand, settings, download, and pagination. Add `aria-label` and `title`.
- Do not introduce one-off visual systems. Match existing spacing, color, typography, component density, and page structure.
- Do not add new dependencies unless the task genuinely needs them and the tradeoff is documented.

## Validation

Use targeted commands that match the touched surface:

```bash
cd frontend && npm run test -- tests/<focused-test>.test.tsx
cd frontend && npm run test -- tests/<focused-test>.test.ts
cd frontend && npm run build
cd frontend && npm run test:e2e -- <focused-spec>.spec.ts
```

When a dev server, watcher, or long-running preview is needed, run it through the project's background-task convention and report the URL.

## Output

Report:

- user-facing behavior changed
- files changed
- version bump, if any
- validation commands and results
- remaining browser/device/terminal risk if not fully covered
"""

BACKEND_DEVELOPMENT_SKILL_MD = """---
name: backend-development
description: Implement, debug, or review Web Terminal ACP backend work using FastAPI, Pydantic v2, SQLAlchemy async, Alembic, pytest, context-based architecture, client-agent runtime, remote-client bootstrap packaging, and backend API/test conventions. Use for API routes, application services, domain rules, repositories/adapters, database queries, migrations, background jobs, terminal runtime, clients, agent profiles, artifacts, workspace, activity, and backend tests.
---

# Backend Development

Use this skill for Web Terminal ACP backend implementation and debugging.

## Stack

- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy async, Alembic, pytest, pytest-asyncio, uvicorn, Redis, PostgreSQL, Elasticsearch, tmux/PTY/runtime adapters.
- Main source: `backend/app`; tests: `backend/tests`; migrations: `backend/alembic`.
- Backend business code is organized by vertical context under `backend/app/contexts`.

## Workflow

1. Read `AGENTS.md`, `backend/pyproject.toml`, nearby context modules, nearby tests, and any frontend contract if the API response is user-facing.
2. Identify the owning context before editing. Add new behavior to `contexts/**`, `platform/**`, or `shared/**`, not legacy horizontal facades.
3. Place route schemas and HTTP error mapping in `api/`; orchestration and use cases in `application/`; pure rules and value objects in `domain/`; persistence and external adapters in `infrastructure/`.
4. Avoid cross-context infrastructure imports. Call another context's application service, DTO, or public projection instead.
5. Add or update focused tests at the canonical module path. Add compatibility tests only when a legacy import path must keep working.
6. Keep backend changes aligned with frontend API clients and types when contracts change.
7. Run focused pytest first, then broader backend tests when shared infrastructure, config, routing, migrations, or client-agent startup is affected.

## Project Constraints

- Legacy paths such as `backend/app/routers/**`, `services/**`, `repositories/**`, `domain/**`, `schemas/**`, `agent_tools/**`, `agent_plugins/**`, and `artifact_plugins/**` are compatibility facades only. Do not add new behavior there.
- Domain modules must not import FastAPI, DB sessions, application services, API schemas, or infrastructure adapters.
- API modules should delegate behavior to application services instead of embedding business logic.
- For slow SQL or PostgreSQL performance work, use the `slow-sql-analysis` skill when available and record the investigation under `docs/performance-tuning/slow-sqls/`.
- For remote-client bootstrap packaging, trace file-level `app.*` imports for every bundled module. Any import that resolves under `backend/app` must be included in `backend/app/contexts/clients/infrastructure/bootstrap_installer.py::client_app_file_contents()` and covered by `test_client_app_file_contents_includes_file_level_app_imports` plus isolated bundle import tests.
- If a remote client fails before WebSocket hello, inspect remote `~/.web-terminal-acp/logs/client.stdout.log` (stdout/stderr capture) and `~/.web-terminal-acp/logs/client.log` (rotated Python logger output) for `ImportError` or `ModuleNotFoundError`; this usually means the slim bootstrap bundle is missing a file.
- If migrations change, run the project migration conflict gate before landing and confirm Alembic has a unique single head.
- Avoid new dependencies unless the task requires them and the deployment/bootstrap impact is covered.

## Validation

Use targeted commands that match the touched surface:

```bash
cd backend && uv run pytest tests/unit/<focused-test>.py -q
cd backend && uv run pytest tests/integration/<focused-test>.py -q
cd backend && uv run pytest tests/unit/test_bootstrap_installer_bundle.py -q
cd backend && uv run pytest tests/unit/test_models_schema_constraints.py::test_alembic_revision_graph_has_unique_single_head -q
```

For a migration upgrade check:

```bash
cd backend
tmp_db="$(mktemp -u /tmp/web-terminal-alembic-XXXXXX.db)"
DATABASE_URL="sqlite+aiosqlite:///$tmp_db" uv run alembic upgrade head
rm -f "$tmp_db"
```

## Output

Report:

- owning context and behavior changed
- API/schema/DB/runtime contract changes
- files changed
- validation commands and results
- migration, bootstrap, remote-client, or performance risk if applicable
"""
