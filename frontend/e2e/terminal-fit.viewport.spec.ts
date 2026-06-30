import * as s from "./terminal-fit.support";

s.test.describe("terminal viewport fit", () => {
  s.test("fills workspace on fast load", async ({ page }) => {
    await s.mockApi(page);
    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    const metrics = await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");
    s.expect(metrics.fillRatio).toBeGreaterThanOrEqual(0.9);
    s.expect(metrics.renderedHeight).toBeGreaterThan(300);
    s.expect(metrics.visibleText).toContain("top marker");
    s.expect(metrics.visibleText).toContain("fit-row-40");
  });
  s.test("does not duplicate activity polling on initial terminal load", async ({ page }) => {
    const activityQueries: string[] = [];
    await s.mockApi(page, {
      onRequest: (url) => {
        if (url.pathname.endsWith("/windows/activity")) {
          activityQueries.push(url.searchParams.toString());
        }
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");

    await s.expect.poll(() => activityQueries.length, { timeout: 5000 }).toBe(1);
    const activityParams = new URLSearchParams(activityQueries[0]);
    s.expect(activityParams.get("include_runtime_tags")).toBe("true");
    s.expect(activityParams.get("project_path")).toBe("/tmp");
  });
  s.test("Alt+L locates the selected terminal in the sidebar list", async ({ page }) => {
    const selectedWindow = s.testWindow();
    const extraWindows = Array.from({ length: 28 }, (_, index) => {
      const suffix = String(index + 1).padStart(2, "0");
      return {
        id: `00000000-0000-0000-0000-0000000010${suffix}`,
        title: `Scrollable Terminal ${suffix}`,
        status: "ACTIVE",
        title_tags: [`scroll-${suffix}`],
        created_at: selectedWindow.created_at,
      };
    });

    await s.mockApi(page, {
      tree: [{
        id: "00000000-0000-0000-0000-000000000010",
        name: "未分类",
        path: "/未分类",
        folders: [],
        windows: [selectedWindow, ...extraWindows],
      }],
    });
    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    const selectedTerminal = page.locator(".tree-window.selected", { hasText: selectedWindow.title });
    await s.expect(selectedTerminal).toBeVisible();

    await page.locator(".sidebar").evaluate((sidebar) => {
      sidebar.scrollTop = sidebar.scrollHeight;
    });
    await s.expect.poll(
      () => selectedTerminal.evaluate((element) => {
        const sidebar = element.closest(".sidebar");
        if (!(sidebar instanceof HTMLElement)) {
          return false;
        }
        const elementBox = element.getBoundingClientRect();
        const sidebarBox = sidebar.getBoundingClientRect();
        return elementBox.bottom > sidebarBox.top && elementBox.top < sidebarBox.bottom;
      }),
      { timeout: 5000 },
    ).toBe(false);

    await page.keyboard.press("Alt+L");

    await s.expect(selectedTerminal).toHaveClass(/locating/);
    await s.expect.poll(
      () => page.evaluate(() => document.activeElement?.classList.contains("xterm-helper-textarea") ?? false),
      { timeout: 5000 },
    ).toBe(true);
    await s.expect.poll(
      () => selectedTerminal.evaluate((element) => {
        const sidebar = element.closest(".sidebar");
        if (!(sidebar instanceof HTMLElement)) {
          return false;
        }
        const elementBox = element.getBoundingClientRect();
        const sidebarBox = sidebar.getBoundingClientRect();
        return elementBox.top >= sidebarBox.top && elementBox.bottom <= sidebarBox.bottom;
      }),
      { timeout: 5000 },
    ).toBe(true);
  });
  s.test("Alt+W switcher fits narrow mobile viewports", async ({ page }) => {
    const now = "2026-05-25T13:45:00.000Z";
    const selectedWindow = s.testWindow();
    const longProjectPath = "/workspace/really-long-project-name-with-many-segments/apps/mobile-web-terminal/client";
    const windows = [
      {
        ...selectedWindow,
        title: "Playwright mobile terminal with an intentionally long title that should not overflow",
      },
      ...Array.from({ length: 4 }, (_, index) => {
        const suffix = String(index + 1).padStart(2, "0");
        return {
          id: `00000000-0000-0000-0000-0000000020${suffix}`,
          title: `Agent workspace ${suffix} with verbose terminal task title and project metadata`,
          status: "ACTIVE",
          title_tags: [`mobile-${suffix}`],
          created_at: now,
        };
      }),
    ];

    await page.setViewportSize({ width: 390, height: 844 });
    await s.mockApi(page, {
      tree: [{
        id: "00000000-0000-0000-0000-000000000010",
        name: "移动端终端切换测试分组",
        path: "/移动端终端切换测试分组",
        folders: [],
        windows,
      }],
      activity: {
        windows: windows.map((window, index) => ({
          window_id: window.id,
          work_status: selectedWindow.work_status,
          runtime_tags: ["codex", `${longProjectPath}-${index}`],
          last_agent_task_completed_at: null,
          git_worktree: null,
        })),
      },
      recents: {
        items: windows.map((window) => ({
          window_id: window.id,
          title: window.title,
          last_used_at: now,
        })),
        page: 1,
        page_size: 20,
        total: windows.length,
        total_pages: 1,
      },
    });
    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    await page.keyboard.press("Alt+W");
    await s.expect(page.locator(".terminal-switcher")).toBeVisible();
    await s.expect.poll(
      () => page.locator(".switcher-window").count(),
      { timeout: 5000 },
    ).toBeGreaterThan(1);

    const metrics = await page.evaluate(() => {
      const viewportWidth = document.documentElement.clientWidth;
      const dialog = document.querySelector(".terminal-switcher");
      const rows = Array.from(document.querySelectorAll(".switcher-window"));
      const metaRows = Array.from(document.querySelectorAll(".switcher-window-meta"));
      const rects = [dialog, ...rows, ...metaRows]
        .filter((element): element is Element => element instanceof Element)
        .map((element) => element.getBoundingClientRect());

      return {
        viewportWidth,
        documentScrollWidth: document.documentElement.scrollWidth,
        maxRight: Math.max(...rects.map((rect) => rect.right)),
        minLeft: Math.min(...rects.map((rect) => rect.left)),
        dialogWidth: dialog instanceof HTMLElement ? dialog.getBoundingClientRect().width : 0,
        rowCount: rows.length,
      };
    });

    s.expect(metrics.rowCount).toBeGreaterThan(1);
    s.expect(metrics.documentScrollWidth).toBeLessThanOrEqual(metrics.viewportWidth);
    s.expect(metrics.minLeft).toBeGreaterThanOrEqual(0);
    s.expect(metrics.maxRight).toBeLessThanOrEqual(metrics.viewportWidth);
    s.expect(metrics.dialogWidth).toBeLessThanOrEqual(374);
  });
  s.test("reconnects and focuses terminal after page reload", async ({ page }) => {
    let connectedCount = 0;

    await s.mockApi(page, {
      afterTerminalConnected: () => {
        connectedCount += 1;
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await s.expect.poll(() => connectedCount, { timeout: 5000 }).toBeGreaterThanOrEqual(1);
    await s.expect.poll(
      () => page.evaluate(() => document.querySelector(".terminal-connection-status")?.textContent ?? null),
      { timeout: 5000 },
    ).toBeNull();

    await page.locator(".terminal-xterm-host").click({ position: { x: 20, y: 20 } });
    await s.expect.poll(
      () => page.evaluate((storageKey) => {
        const raw = window.localStorage.getItem(storageKey);
        if (raw === null) {
          return null;
        }
        try {
          const parsed = JSON.parse(raw) as { viewId?: unknown };
          return typeof parsed.viewId === "string" ? parsed.viewId : null;
        } catch {
          return null;
        }
      }, s.TERMINAL_ACTIVE_VIEW_STORAGE_KEY),
      { timeout: 5000 },
    ).not.toBeNull();
    const previousViewId = await page.evaluate((storageKey) => {
      const raw = window.localStorage.getItem(storageKey);
      return raw === null ? null : (JSON.parse(raw) as { viewId: string }).viewId;
    }, s.TERMINAL_ACTIVE_VIEW_STORAGE_KEY);

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await s.expect.poll(() => connectedCount, { timeout: 5000 }).toBeGreaterThanOrEqual(2);
    await s.expect.poll(
      () => page.evaluate(() => document.querySelector(".terminal-connection-status")?.textContent ?? null),
      { timeout: 5000 },
    ).toBeNull();
    await s.expect.poll(
      () => page.evaluate(() => document.activeElement?.classList.contains("xterm-helper-textarea") ?? false),
      { timeout: 5000 },
    ).toBe(true);

    const reloadedViewId = await page.evaluate((storageKey) => {
      const raw = window.localStorage.getItem(storageKey);
      return raw === null ? null : (JSON.parse(raw) as { viewId: string }).viewId;
    }, s.TERMINAL_ACTIVE_VIEW_STORAGE_KEY);
    s.expect(reloadedViewId).not.toBeNull();
    s.expect(reloadedViewId).not.toBe(previousViewId);
  });
  s.test("shows the terminal when opened directly on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await s.mockApi(page);

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".mobile-terminal-active .xterm-rows", { timeout: 30_000 });

    const shellClass = await page.locator(".app-shell").getAttribute("class");
    s.expect(shellClass).toContain("mobile-terminal-active");

    const metrics = await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");
    s.expect(metrics.workspaceHeight).toBeGreaterThan(700);
    s.expect(metrics.hostHeight).toBeGreaterThan(600);
    s.expect(metrics.visibleText).toContain("fit-row-40");
  });
  s.test("stays responsive when mobile quick input squeezes virtual keys", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      const visualViewportListeners = new Map<string, Set<EventListenerOrEventListenerObject>>();
      const dispatchVisualViewportEvent = (type: string) => {
        const event = new Event(type);
        for (const listener of visualViewportListeners.get(type) ?? []) {
          if (typeof listener === "function") {
            listener.call(window.visualViewport, event);
          } else {
            listener.handleEvent(event);
          }
        }
      };
      const visualViewport = {
        width: 390,
        height: 844,
        offsetLeft: 0,
        offsetTop: 0,
        pageLeft: 0,
        pageTop: 0,
        scale: 1,
        addEventListener: (type: string, listener: EventListenerOrEventListenerObject | null) => {
          if (listener === null) {
            return;
          }
          const listeners = visualViewportListeners.get(type) ?? new Set<EventListenerOrEventListenerObject>();
          listeners.add(listener);
          visualViewportListeners.set(type, listeners);
        },
        removeEventListener: (type: string, listener: EventListenerOrEventListenerObject | null) => {
          if (listener === null) {
            return;
          }
          visualViewportListeners.get(type)?.delete(listener);
        },
        dispatchEvent: (event: Event) => {
          dispatchVisualViewportEvent(event.type);
          return true;
        },
      };
      Object.defineProperty(window, "visualViewport", {
        value: visualViewport,
        configurable: true,
      });
      Object.defineProperty(window, "__setVisualViewportHeight", {
        value: (height: number) => {
          visualViewport.height = height;
          dispatchVisualViewportEvent("resize");
        },
        configurable: true,
      });

      const state = {
        resizeObserverCallbacks: 0,
        renderResizeObserverCallbacks: 0,
        resizeMessages: 0,
        maxTimerDelayMs: 0,
        lastTickAt: performance.now(),
      };
      Object.defineProperty(window, "__mobileKeyboardSqueeze", {
        value: state,
        configurable: true,
      });

      window.setInterval(() => {
        const now = performance.now();
        state.maxTimerDelayMs = Math.max(state.maxTimerDelayMs, now - state.lastTickAt);
        state.lastTickAt = now;
      }, 50);

      const NativeResizeObserver = window.ResizeObserver;
      class InstrumentedResizeObserver extends NativeResizeObserver {
        constructor(callback: ResizeObserverCallback) {
          super((entries, observer) => {
            state.resizeObserverCallbacks += 1;
            if (entries.some((entry) => {
              const target = entry.target;
              return target instanceof HTMLElement
                && (
                  target.matches(".xterm-screen canvas")
                  || target.matches(".xterm-rows")
                );
            })) {
              state.renderResizeObserverCallbacks += 1;
            }
            callback(entries, observer);
          });
        }
      }
      Object.defineProperty(window, "ResizeObserver", {
        value: InstrumentedResizeObserver,
        configurable: true,
      });

      const originalPostMessage = Worker.prototype.postMessage;
      Worker.prototype.postMessage = function postMessage(message: unknown, transfer?: Transferable[]) {
        if (
          typeof message === "object"
          && message !== null
          && "type" in message
          && (message as { type?: unknown }).type === "json"
        ) {
          const rawData = (message as { data?: unknown }).data;
          if (typeof rawData === "string") {
            try {
              const parsed = JSON.parse(rawData) as { type?: unknown };
              if (parsed.type === "resize") {
                state.resizeMessages += 1;
              }
            } catch {
              // Ignore non-JSON worker payloads.
            }
          }
        }
        return originalPostMessage.call(this, message, transfer ?? []);
      };
    });
    await s.mockApi(page);

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".mobile-terminal-active .xterm-rows", { timeout: 30_000 });
    await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");

    const virtualKeys = page.locator(".terminal-virtual-keys");
    if (!await virtualKeys.isVisible()) {
      await page.getByRole("button", { name: "Controls" }).click();
      await page.getByRole("menuitem", { name: /Virtual keys/ }).click();
    }
    await s.expect(virtualKeys).toBeVisible();

    await page.keyboard.press("Alt+I");
    const quickInput = page.getByLabel("Quick terminal input");
    await s.expect(quickInput).toBeFocused();

    const beforeSqueeze = await page.evaluate(() => ({
      ...(window as Window & {
        __mobileKeyboardSqueeze?: {
          resizeObserverCallbacks: number;
          renderResizeObserverCallbacks: number;
          resizeMessages: number;
          maxTimerDelayMs: number;
          lastTickAt: number;
        };
      }).__mobileKeyboardSqueeze,
    }));
    await page.evaluate(() => {
      const state = (window as Window & {
        __mobileKeyboardSqueeze?: {
          maxTimerDelayMs: number;
          lastTickAt: number;
        };
      }).__mobileKeyboardSqueeze;
      if (state !== undefined) {
        state.maxTimerDelayMs = 0;
        state.lastTickAt = performance.now();
      }
    });

    await page.evaluate(() => {
      (window as Window & {
        __setVisualViewportHeight?: (height: number) => void;
      }).__setVisualViewportHeight?.(340);
    });
    await quickInput.fill("soft keyboard squeeze");
    await page.waitForTimeout(1500);

    await s.expect(quickInput).toHaveValue("soft keyboard squeeze");
    await s.expect(page.locator(".terminal-virtual-keys")).toBeVisible();
    await s.expect.poll(
      () => page.evaluate(() => {
        const shell = document.querySelector(".app-shell");
        return shell instanceof HTMLElement ? shell.getBoundingClientRect().height : 0;
      }),
      { timeout: 3000 },
    ).toBeLessThanOrEqual(360);

    const afterSqueeze = await page.evaluate(() => ({
      ...(window as Window & {
        __mobileKeyboardSqueeze?: {
          resizeObserverCallbacks: number;
          renderResizeObserverCallbacks: number;
          resizeMessages: number;
          maxTimerDelayMs: number;
          lastTickAt: number;
        };
      }).__mobileKeyboardSqueeze,
    }));
    s.expect(afterSqueeze.resizeObserverCallbacks - beforeSqueeze.resizeObserverCallbacks).toBeLessThan(60);
    s.expect(afterSqueeze.renderResizeObserverCallbacks - beforeSqueeze.renderResizeObserverCallbacks).toBeLessThan(20);
    s.expect(afterSqueeze.resizeMessages - beforeSqueeze.resizeMessages).toBeLessThan(12);
    s.expect(afterSqueeze.maxTimerDelayMs).toBeLessThan(250);
  });
  s.test("fills workspace when tree API is slow", async ({ page }) => {
    await s.mockApi(page, { slowTreeMs: 6000 });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    const metrics = await s.waitForFilledTerminal(page, 0.9, 90_000, "fit-row-40");
    s.expect(metrics.fillRatio).toBeGreaterThanOrEqual(0.9);
  });
});
