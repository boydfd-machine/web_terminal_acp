# AGENTS.md

## Client Versioning

- Any client-side change must include a version bump in the same change set.
- Use Semantic Versioning (`MAJOR.MINOR.PATCH`) as the default convention.
- Increment `MAJOR` for incompatible protocol, API, storage, or deployment changes that require coordinated upgrades.
- Increment `MINOR` for backward-compatible client features or behavior additions.
- Increment `PATCH` for backward-compatible bug fixes, small UI adjustments, refactors, or internal-only client changes.
- Keep all project version sources that represent the client in sync, such as `backend/app/version.py` and `frontend/package.json` when applicable.

## Web Terminal Agent 开发

在 Web Terminal 管理 shell（已设置 `WEB_TERMINAL_WINDOW_ID`）中跑 agent 时，**必须先读取并严格遵循**项目 skill：

**`.cursor/skills/web-terminal-git-worktree`**（`web-terminal-git-worktree`）

禁止在主仓库 checkout 直接改功能代码；禁止让用户代替 agent 手工 `git worktree add`。worktree 创建、进入、注册与清理均按该 skill 中的脚本与流程执行。**任务完成后必须把 `agent/<suffix>` 合并回 `main`**（见 skill Step 4），不要只留在 worktree 分支上。

## Web Terminal 性能优先级

Web Terminal 的性能优化和回归判断必须按以下优先级排序：

1. 用户针对 terminal 的输入输出显示是最高优先级。用户输入必须瞬间反应，屏幕显示也必须瞬间反应；这是最终最核心的体验部分，必须有足够的自动化测试和回归覆盖。
2. 各种状态展示是第二优先级。
3. Agent record 和命令历史是第三优先级。
4. Git worktree 状态是第四优先级。

当这些目标发生冲突时，优先保护第一优先级的 terminal 输入、输出和屏幕显示延迟，不允许为了状态、agent record、命令历史或 git worktree 状态牺牲第一优先级体验。

Terminal 显示必须以服务端 terminal 二进制输出流为唯一事实来源；不要用本地乐观回显、屏幕内容猜测、输入时清空输出队列，或任何会丢弃/重排 terminal 字节流的优化来换取表面延迟。
