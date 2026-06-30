import * as s from "./terminal-fit.support";

type BoundsReport = {
  documentScrollWidth: number;
  viewportWidth: number;
  offenders: Array<{
    className: string;
    tagName: string;
    text: string;
    left: number;
    right: number;
    width: number;
  }>;
};

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const report = await page.evaluate<BoundsReport>(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const isInsideHorizontalScroller = (element: HTMLElement) => {
      let current: HTMLElement | null = element.parentElement;
      while (current !== null && current !== document.body) {
        const style = window.getComputedStyle(current);
        if (
          current.scrollWidth > current.clientWidth + 1
          && ["auto", "scroll"].includes(style.overflowX)
        ) {
          return true;
        }
        current = current.parentElement;
      }
      return false;
    };
    const isVisibleForLayout = (element: HTMLElement) => {
      if (element.classList.contains("xterm-char-measure-element")) {
        return false;
      }
      let current: HTMLElement | null = element;
      while (current !== null && current !== document.body) {
        const style = window.getComputedStyle(current);
        if (
          style.display === "none"
          || style.visibility === "hidden"
          || style.opacity === "0"
          || current.getAttribute("aria-hidden") === "true"
        ) {
          return false;
        }
        current = current.parentElement;
      }
      return true;
    };
    const offenders = Array.from(document.body.querySelectorAll("*"))
      .filter((element): element is HTMLElement => element instanceof HTMLElement)
      .filter(isVisibleForLayout)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          element,
          rect,
        };
      })
      .filter(({ rect }) => (
        rect.width > 1
        && rect.height > 1
        && (rect.left < -1 || rect.right > viewportWidth + 1)
      ))
      .filter(({ element }) => !isInsideHorizontalScroller(element))
      .slice(0, 12)
      .map(({ element, rect }) => ({
        className: String(element.className),
        tagName: element.tagName.toLowerCase(),
        text: (element.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 80),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
      }));

    return {
      documentScrollWidth: document.documentElement.scrollWidth,
      viewportWidth,
      offenders,
    };
  });

  s.expect(report.documentScrollWidth, JSON.stringify(report, null, 2)).toBeLessThanOrEqual(report.viewportWidth);
  s.expect(report.offenders, JSON.stringify(report, null, 2)).toEqual([]);
}

async function waitForElementWithinViewport(page: import("@playwright/test").Page, selector: string) {
  await s.expect.poll(
    () => page.locator(selector).evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = document.documentElement.clientHeight;
      return rect.left >= -1
        && rect.right <= viewportWidth + 1
        && rect.top >= -1
        && rect.bottom <= viewportHeight + 1;
    }),
    { timeout: 5_000 },
  ).toBe(true);
}

async function waitForElementHiddenForLayout(page: import("@playwright/test").Page, selector: string) {
  await s.expect.poll(
    () => page.locator(selector).evaluate((element) => {
      const style = window.getComputedStyle(element);
      return style.display === "none" || style.visibility === "hidden" || style.opacity === "0";
    }),
    { timeout: 5_000 },
  ).toBe(true);
}

async function openMobileTerminal(page: import("@playwright/test").Page, viewport = { width: 390, height: 844 }) {
  await page.setViewportSize(viewport);
  await s.mockApi(page);
  await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".mobile-terminal-active .xterm-rows", { timeout: 30_000 });
  await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");
}

function mobileTodoApiPayloads() {
  const now = "2026-06-05T00:00:00Z";
  const type = {
    id: "default",
    scope: "system",
    client_id: null,
    project_path: null,
    name: "Default",
    description: "Default project todo card type.",
    agent: "codex",
    agent_profile_id: null,
    artifact_kinds: ["page_review_cards"],
    dispatch_template: null,
    created_at: now,
    updated_at: now,
  };
  const assignedTerminal = {
    id: s.LOCAL_WINDOW_ID,
    title: "Mobile todo terminal with a long title",
    summary: null,
    title_tags: ["mobile"],
    runtime_tags: ["codex", "/tmp"],
    work_status: { state: "RECENT_ACTIVE", label: "recent active", color: "green", last_activity_at: now },
    topic_path: "/tmp",
    git_worktree: null,
    created_at: now,
  };
  const base = {
    id: "todo-mobile",
    client_id: s.LOCAL_CLIENT_ID,
    project_path: "/tmp",
    todo_type_id: "default",
    todo_type: type,
    title: "Mobile todo with a deliberately long title that must wrap inside phone dialogs",
    description: "Long mobile details ".repeat(18),
    status: "TODO",
    sort_order: 1,
    assigned_window_id: s.LOCAL_WINDOW_ID,
    assigned_agent: "codex",
    agent_profile_id: null,
    dispatch_prompt: null,
    dispatch_stage: null,
    dispatch_error: null,
    dispatched_at: null,
    awaiting_review_at: null,
    completed_at: null,
    review_strategy: "LOCAL_CARD",
    review_status: "NOT_REQUESTED",
    review_agent: null,
    review_agent_profile_id: null,
    review_window_id: null,
    review_prompt: null,
    review_dispatched_at: null,
    reviewed_at: null,
    review_unseen: false,
    needs_human_review: false,
    review_notes: null,
    implementation_worktree: null,
    execution_kind: "PERIODIC",
    terminal_policy: "NEW_TERMINAL",
    trigger_strategy: "CRON",
    cron_expression: "0 9 * * 1",
    schedule_enabled: true,
    next_trigger_at: null,
    last_triggered_at: null,
    execution_run_count: 0,
    artifact_kinds: ["page_review_cards"],
    assigned_terminal: assignedTerminal,
    execution_runs: [],
    artifacts: [],
    dependencies: [{ id: "todo-done", title: "Finished upstream task", status: "DONE", completed_at: now }],
    dependents: [],
    referenced_todos: [],
    queued_dispatch: false,
    created_at: now,
    updated_at: now,
  };
  const upstream = {
    ...base,
    id: "todo-done",
    title: "Finished upstream task",
    description: "Already done.",
    status: "DONE",
    sort_order: 2,
    assigned_window_id: null,
    assigned_terminal: null,
    dependencies: [],
    artifact_kinds: [],
  };
  return { type, todos: [base, upstream] };
}

async function mockMobileTodoApi(page: import("@playwright/test").Page) {
  const payloads = mobileTodoApiPayloads();
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (payload: unknown) => route.fulfill({
      status: 200,
      headers: { "Access-Control-Allow-Origin": "*", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (method === "OPTIONS") {
      await route.fulfill({ status: 204, headers: { "Access-Control-Allow-Origin": "*" } });
      return;
    }
    if (path.endsWith("/projects/todos") && method === "GET") {
      await json({ todos: payloads.todos });
      return;
    }
    if (path.includes("/projects/todos/") && method === "GET") {
      const todoId = decodeURIComponent(path.split("/projects/todos/")[1].split("/")[0]);
      await json(payloads.todos.find((todo) => todo.id === todoId) ?? payloads.todos[0]);
      return;
    }
    if (path.endsWith("/projects/todo-types")) {
      await json({ todo_types: [payloads.type] });
      return;
    }
    if (path === "/api/artifact-plugins") {
      await json({ plugins: [{
        domain: "project",
        artifact_kind: "page_review_cards",
        label: "Page review cards",
        default_title: "Page review",
        origin: "built_in",
        editable: false,
        plugin_format: "template",
        downloadable: false,
      }] });
      return;
    }
    if (path.endsWith("/agent-clients")) {
      await json({ agent_clients: [{ id: "codex", provider_id: "codex", label: "Codex", aliases: [], default_command: "codex", command_names: ["codex"], capabilities: { launch: true, client_config: false } }] });
      return;
    }
    if (path.endsWith("/agent-profiles")) {
      await json({ profiles: [] });
      return;
    }
    if (path === "/api/system-agent-config/model-presets") {
      await json({ presets: [] });
      return;
    }
    await route.fallback();
  });
}

s.test.describe("mobile layout", () => {
  s.test("keeps the terminal shell and controls within a phone viewport", async ({ page }) => {
    await openMobileTerminal(page);
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: "Controls" }).click();
    await s.expect(page.getByRole("menu")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("menuitem", { name: "Details" }).click();
    await s.expect(page.locator(".detail-panel")).toBeVisible();
    await waitForElementWithinViewport(page, ".detail-panel");
    await s.expect(page.locator(".mobile-shortcut-fab-ball")).toHaveCount(0);
    await expectNoHorizontalOverflow(page);

    await page.locator(".detail-panel").getByRole("button", { name: "Close" }).click();
    await s.expect(page.locator(".detail-panel")).not.toBeVisible();
    await waitForElementHiddenForLayout(page, ".detail-panel");
    await s.expect(page.locator(".mobile-shortcut-fab-ball")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  s.test("keeps mobile overlays bounded and usable", async ({ page }) => {
    await openMobileTerminal(page, { width: 360, height: 780 });

    await page.getByRole("button", { name: "Controls" }).click();
    await page.getByRole("menuitem", { name: /Settings|设置/ }).click();
    await s.expect(page.getByRole("dialog", { name: /Settings|设置/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.getByRole("button", { name: /Close|关闭/ }).click();

    await page.locator(".mobile-shortcut-fab-ball").click();
    await s.expect(page.locator(".mobile-shortcut-fab-drawer")).toBeVisible();
    await page.getByRole("menuitem", { name: /按项目新建/ }).click();
    await s.expect(page.getByRole("dialog").filter({ hasText: "New terminal by project path" })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: "Codex" }).click();
    await page.getByRole("button", { name: "配置" }).click();
    await s.expect(page.getByRole("dialog", { name: "Create terminal" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  s.test("moves the mobile shortcut button after long press with early finger drift", async ({ page }) => {
    await openMobileTerminal(page, { width: 360, height: 780 });

    const button = page.locator(".mobile-shortcut-fab-ball");
    await s.expect(button).toBeVisible();
    const initialBox = await button.boundingBox();
    if (initialBox === null) {
      throw new Error("mobile shortcut button did not have a layout box");
    }

    const startX = initialBox.x + initialBox.width / 2;
    const startY = initialBox.y + initialBox.height / 2;
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 1 });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: startX, y: startY }] });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: startX - 16, y: startY - 16 }] });
    await page.waitForTimeout(430);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: 112, y: 156 }] });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });

    await s.expect.poll(
      async () => {
        const movedBox = await button.boundingBox();
        if (movedBox === null) {
          return null;
        }
        return {
          x: Math.round(movedBox.x),
          y: Math.round(movedBox.y),
        };
      },
      { timeout: 5_000 },
    ).toEqual({ x: 84, y: 128 });

    await s.expect(page.locator(".mobile-shortcut-fab-drawer")).toHaveCount(0);
  });

  s.test("keeps project todo mobile panels bounded and usable", async ({ page }) => {
    await mockMobileTodoApi(page);
    await openMobileTerminal(page, { width: 360, height: 780 });

    await page.getByRole("button", { name: "Kanban" }).click();
    await s.expect(page.locator(".project-kanban-workspace")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /View settings/ }).click();
    await s.expect(page.locator(".project-todo-board-settings-popover")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    const mobileTodoCard = page.locator(".project-todo-card").filter({ hasText: "Mobile todo" }).first();
    await mobileTodoCard.locator(".project-todo-card-main").click();
    await s.expect(page.getByRole("dialog", { name: "Todo details" })).toBeVisible();
    await waitForElementWithinViewport(page, ".project-todo-detail-dialog");
    await expectNoHorizontalOverflow(page);

    const todoDetailsDialog = page.getByRole("dialog", { name: "Todo details" });
    await todoDetailsDialog.getByRole("button", { name: "Comment", exact: true }).click();
    await s.expect(page.getByRole("dialog", { name: "Comment on todo" })).toBeVisible();
    await waitForElementWithinViewport(page, ".project-todo-comment-modal");
    await expectNoHorizontalOverflow(page);
    await page.getByRole("button", { name: "Close comment" }).click();
    await s.expect(page.getByRole("dialog", { name: "Comment on todo" })).not.toBeVisible();

    await mobileTodoCard.getByRole("button", { name: /Dispatch Mobile todo/ }).click();
    await s.expect(page.getByRole("dialog", { name: "Create terminal" })).toBeVisible();
    await waitForElementWithinViewport(page, ".terminal-create-modal");
    await expectNoHorizontalOverflow(page);
    await page.getByRole("button", { name: "关闭" }).click();
    await s.expect(page.getByRole("dialog", { name: "Create terminal" })).not.toBeVisible();

    await page.getByRole("button", { name: "New task" }).click();
    await s.expect(page.getByRole("dialog", { name: "New task" })).toBeVisible();
    await waitForElementWithinViewport(page, ".project-todo-create-dialog");
    await expectNoHorizontalOverflow(page);
    await page.getByRole("button", { name: "Close new task" }).click();

    await page.getByRole("button", { name: "卡片类型管理" }).click();
    await s.expect(page.getByRole("dialog", { name: "卡片类型管理" })).toBeVisible();
    await waitForElementWithinViewport(page, ".project-todo-type-manager-modal");
    await expectNoHorizontalOverflow(page);
  });
});
