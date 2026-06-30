import * as s from "./terminal-fit.support";

s.test.describe("terminal viewport fit", () => {
  s.test("fills workspace when terminal websocket is slow", async ({ page }) => {
    await s.mockApi(page, { slowSocketMs: 8000 });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    const metrics = await s.waitForFilledTerminal(page, 0.9, 90_000, "fit-row-40");
    s.expect(metrics.fillRatio).toBeGreaterThanOrEqual(0.9);
  });
  s.test("fills workspace when tree and websocket are both slow", async ({ page }) => {
    await s.mockApi(page, { slowTreeMs: 5000, slowSocketMs: 8000 });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    const metrics = await s.waitForFilledTerminal(page, 0.9, 120_000, "fit-row-40");
    s.expect(metrics.fillRatio).toBeGreaterThanOrEqual(0.9);
  });
  s.test("stays filled after delayed layout settle", async ({ page }) => {
    await s.mockApi(page, { slowTreeMs: 4000 });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await s.waitForFilledTerminal(page, 0.9, 90_000, "fit-row-40");

    await page.waitForTimeout(3000);
    const afterSettle = await s.readTerminalMetrics(page);
    s.expect(afterSettle).not.toBeNull();
    s.expect(afterSettle!.fillRatio).toBeGreaterThanOrEqual(0.9);
  });
  s.test("captures a full visible terminal screenshot", async ({ page }) => {
    await s.mockApi(page, { slowSocketMs: 1500 });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    const metrics = await s.waitForFilledTerminal(page, 0.92, 90_000, "bottom marker");
    s.expect(metrics.connectionStatus).toBeNull();
    s.expect(metrics.visibleText).toContain("top marker");
    s.expect(metrics.visibleText).toContain("fit-row-40");
    s.expect(metrics.visibleText).toContain("bottom marker");
    s.expect(metrics.renderedHeight).toBeGreaterThan(700);
    await page.screenshot({ path: s.TERMINAL_SCREENSHOT_PATH, fullPage: false });
  });
  s.test("sends Escape to tmux when terminal already has focus", async ({ page }) => {
    const inputs: string[] = [];
    let resolveEscapeInput: ((text: string) => void) | null = null;
    const escapeInputPromise = new Promise<string>((resolve) => {
      resolveEscapeInput = resolve;
    });

    await s.mockApi(page, {
      onTerminalMessage: (message) => {
        if (!Buffer.isBuffer(message)) {
          return;
        }

        const text = message.toString("utf8");
        inputs.push(text);
        if (text.includes("\x1b")) {
          resolveEscapeInput?.(text);
        }
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await page.locator(".terminal-xterm-host").click({ position: { x: 20, y: 20 } });
    await page.waitForFunction(() => document.activeElement?.classList.contains("xterm-helper-textarea"));

    await page.keyboard.press("Escape");

    const receivedInput = await Promise.race([
      escapeInputPromise,
      page.waitForTimeout(2000).then(() => {
        throw new Error("Timed out waiting for Escape terminal input");
      }),
    ]);
    s.expect(receivedInput).toBe("\x1b");
    await s.expect.poll(
      () => page.evaluate(() => document.activeElement?.classList.contains("xterm-helper-textarea") ?? false),
      { timeout: 2000 },
    ).toBe(true);

    const inputCountAfterEscape = inputs.length;
    await page.keyboard.press("a");
    await s.expect.poll(() => inputs.slice(inputCountAfterEscape).join(""), { timeout: 2000 }).toContain("a");
  });
  s.test("keeps terminal input sends responsive during agent output bursts", async ({ page }) => {
    type ServerPendingInput = {
      expected: string;
      startedAt: number;
      resolve: (delayMs: number) => void;
      reject: (error: Error) => void;
      timer: ReturnType<typeof setTimeout>;
    };

    const pendingInputs: ServerPendingInput[] = [];
    const browserDispatchDelays: number[] = [];
    const serverReceiveDelays: number[] = [];
    const inputSequence = "bcdfhijklmqrsvwxyz!$";
    let burstTimer: ReturnType<typeof setTimeout> | null = null;
    let burstIndex = 0;

    const waitForInput = (expected: string): Promise<number> => new Promise((resolve, reject) => {
      const pending: ServerPendingInput = {
        expected,
        startedAt: Date.now(),
        resolve,
        reject,
        timer: setTimeout(() => {
          const index = pendingInputs.indexOf(pending);
          if (index >= 0) {
            pendingInputs.splice(index, 1);
          }
          reject(new Error(`Timed out waiting for terminal input ${expected}`));
        }, 2000),
      };
      pendingInputs.push(pending);
    });

    await page.addInitScript(() => {
      type BrowserInputRecord = {
        key: string;
        text: string | null;
        keydownAt: number;
        onDataAt?: number;
        preHandlerDelayMs?: number;
        dispatchAt: number;
        delayMs: number;
        echoAt?: number;
        echoDelayMs?: number;
      };
      const records: BrowserInputRecord[] = [];
      const pending: Array<{ key: string; keydownAt: number }> = [];
      const decoder = new TextDecoder();

      Object.defineProperty(window, "__terminalInputDispatchRecords", {
        value: records,
        configurable: true,
      });
      Object.defineProperty(window, "__terminalInputOnDataPending", {
        value: pending,
        configurable: true,
      });

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_TERMINAL_DATA__?: (data: string, onDataAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_TERMINAL_DATA__ = (data, onDataAt) => {
        const index = pending.findIndex((candidate) => data.includes(candidate.key));
        if (index < 0) {
          return;
        }
        const candidate = pending[index];
        const existing = records.find((record) => (
          record.key === candidate.key
          && record.keydownAt === candidate.keydownAt
        ));
        if (existing !== undefined) {
          existing.onDataAt = onDataAt;
          existing.preHandlerDelayMs = onDataAt - candidate.keydownAt;
        }
      };

      window.addEventListener("keydown", (event) => {
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          pending.push({ key: event.key, keydownAt: performance.now() });
        }
      }, { capture: true });

      const originalPostMessage = Worker.prototype.postMessage;
      Worker.prototype.postMessage = function postMessage(message: unknown, transfer?: Transferable[]) {
        if (
          typeof message === "object"
          && message !== null
          && "type" in message
          && (message as { type?: unknown }).type === "input"
        ) {
          const data = (message as { data?: unknown }).data;
          const text = ArrayBuffer.isView(data) ? decoder.decode(data) : null;
          const index = pending.findIndex((candidate) => text.includes(candidate.key));
          if (index >= 0) {
            const [candidate] = pending.splice(index, 1);
            const dispatchAt = performance.now();
            records.push({
              key: candidate.key,
              text,
              keydownAt: candidate.keydownAt,
              onDataAt: dispatchAt,
              preHandlerDelayMs: dispatchAt - candidate.keydownAt,
              dispatchAt,
              delayMs: dispatchAt - candidate.keydownAt,
            });
          }
        }
        return originalPostMessage.call(this, message, transfer ?? []);
      };

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__?: (data: string | Uint8Array, parsedAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__ = (data, parsedAt) => {
        const text = typeof data === "string" ? data : decoder.decode(data);
        for (const record of records) {
          if (record.echoAt !== undefined || record.text === null || !text.includes(record.key)) {
            continue;
          }
          record.echoAt = parsedAt;
          record.echoDelayMs = parsedAt - record.keydownAt;
        }
      };
    });

    await s.mockApi(page, {
      onTerminalMessage: (message, ws) => {
        if (!Buffer.isBuffer(message)) {
          return;
        }
        const text = message.toString("utf8");
        const index = pendingInputs.findIndex((pending) => text.includes(pending.expected));
        ws.send(Buffer.from(text));
        if (index < 0) {
          return;
        }
        const [pending] = pendingInputs.splice(index, 1);
        clearTimeout(pending.timer);
        pending.resolve(Date.now() - pending.startedAt);
      },
      afterTerminalConnected: (ws) => {
        const sendBurst = () => {
          for (let index = 0; index < 80; index += 1) {
            burstIndex += 1;
            ws.send(Buffer.from(`agent-output-${burstIndex} ${"#".repeat(160)}\r\n`));
          }
          if (burstIndex < 8000) {
            burstTimer = setTimeout(sendBurst, 0);
          }
        };
        sendBurst();
      },
    });

    try {
      await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
      await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
      await page.locator(".terminal-xterm-host").click({ position: { x: 20, y: 20 } });
      await page.waitForFunction(() => document.activeElement?.classList.contains("xterm-helper-textarea"));

      for (const expected of inputSequence) {
        const currentBrowserRecordCount = await page.evaluate(() => (
          (window as Window & { __terminalInputDispatchRecords?: unknown[] }).__terminalInputDispatchRecords?.length ?? 0
        ));
        const browserDispatchPromise = page.waitForFunction(
          (count) => (
            (window as Window & { __terminalInputDispatchRecords?: unknown[] }).__terminalInputDispatchRecords?.length ?? 0
          ) > count,
          currentBrowserRecordCount,
          { timeout: 2000 },
        );
        const inputPromise = waitForInput(expected);
        await page.keyboard.type(expected);
        await browserDispatchPromise;
        const browserRecord = await page.evaluate(() => {
          const records = (window as Window & {
            __terminalInputDispatchRecords?: Array<{
              delayMs: number;
              preHandlerDelayMs?: number;
              dispatchAt: number;
              onDataAt?: number;
            }>;
          }).__terminalInputDispatchRecords ?? [];
          return records[records.length - 1] ?? null;
        });
        if (browserRecord !== null) {
          browserDispatchDelays.push(browserRecord.delayMs);
        }
        serverReceiveDelays.push(await inputPromise);
        await page.waitForTimeout(25);
      }
    } finally {
      if (burstTimer !== null) {
        clearTimeout(burstTimer);
      }
      for (const pending of pendingInputs.splice(0)) {
        clearTimeout(pending.timer);
        pending.reject(new Error("Test finished before terminal input was observed"));
      }
    }
    const sorted = [...browserDispatchDelays].sort((left, right) => left - right);
    const p95 = sorted[Math.floor((sorted.length - 1) * 0.95)];
    s.expect(browserDispatchDelays.length).toBe(inputSequence.length);
    s.expect(Math.max(...browserDispatchDelays)).toBeLessThan(10);
    s.expect(p95).toBeLessThan(10);
    s.expect(serverReceiveDelays.length).toBe(inputSequence.length);
  });
  s.test("flushes echoed input promptly when output queue is idle", async ({ page }) => {
    type BrowserInputRecord = {
      key: string;
      keydownAt: number;
      dispatchAt?: number;
      dispatchDelayMs?: number;
      interactiveAt?: number;
      interactiveDelayMs?: number;
      writeAfterInteractiveMs?: number;
      echoAt?: number;
      echoDelayMs?: number;
    };

    await page.addInitScript(() => {
      const records: BrowserInputRecord[] = [];
      const pending: Array<{ key: string; keydownAt: number }> = [];
      const decoder = new TextDecoder();

      Object.defineProperty(window, "__terminalInputEchoRecords", {
        value: records,
        configurable: true,
      });
      Object.defineProperty(window, "__terminalLastWriteAt", {
        value: { current: 0 },
        configurable: true,
      });

      window.addEventListener("keydown", (event) => {
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          pending.push({ key: event.key, keydownAt: performance.now() });
        }
      }, { capture: true });

      const originalPostMessage = Worker.prototype.postMessage;
      Worker.prototype.postMessage = function postMessage(message: unknown, transfer?: Transferable[]) {
        if (
          typeof message === "object"
          && message !== null
          && "type" in message
          && (message as { type?: unknown }).type === "input"
        ) {
          const data = (message as { data?: unknown }).data;
          const text = ArrayBuffer.isView(data) ? decoder.decode(data) : null;
          if (text !== null) {
            const index = pending.findIndex((candidate) => text.includes(candidate.key));
            if (index >= 0) {
              const [candidate] = pending.splice(index, 1);
              const dispatchAt = performance.now();
              records.push({
                key: candidate.key,
                keydownAt: candidate.keydownAt,
                dispatchAt,
                dispatchDelayMs: dispatchAt - candidate.keydownAt,
              });
            }
          }
        }
        return originalPostMessage.call(this, message, transfer ?? []);
      };

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_INTERACTIVE_OUTPUT__?: (data: string | Uint8Array, receivedAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_INTERACTIVE_OUTPUT__ = (data, receivedAt) => {
        const text = typeof data === "string" ? data : decoder.decode(data);
        for (const record of records) {
          if (record.interactiveAt !== undefined || !text.includes(record.key)) {
            continue;
          }
          record.interactiveAt = receivedAt;
          record.interactiveDelayMs = receivedAt - record.keydownAt;
        }
      };

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__?: (data: string | Uint8Array, parsedAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__ = (data, parsedAt) => {
        ((window as Window & {
          __terminalLastWriteAt?: { current: number };
        }).__terminalLastWriteAt ??= { current: 0 }).current = parsedAt;
        const text = typeof data === "string" ? data : decoder.decode(data);
        for (const record of records) {
          if (record.echoAt !== undefined || !text.includes(record.key)) {
            continue;
          }
          record.echoAt = parsedAt;
          record.echoDelayMs = parsedAt - record.keydownAt;
          if (record.interactiveAt !== undefined) {
            record.writeAfterInteractiveMs = parsedAt - record.interactiveAt;
          }
        }
      };
    });

    await s.mockApi(page, {
      onTerminalMessage: (message, ws) => {
        if (Buffer.isBuffer(message)) {
          ws.send(message);
        }
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");
    await page.locator(".terminal-xterm-host").click({ position: { x: 20, y: 20 } });
    await page.waitForFunction(() => document.activeElement?.classList.contains("xterm-helper-textarea"));
    await s.expect.poll(
      () => page.evaluate(() => {
        const lastWriteAt = (window as Window & {
          __terminalLastWriteAt?: { current: number };
        }).__terminalLastWriteAt?.current ?? 0;
        return lastWriteAt > 0 ? performance.now() - lastWriteAt : 0;
      }),
      { timeout: 3000 },
    ).toBeGreaterThan(100);
    await page.keyboard.type("z");

    await s.expect.poll(
      () => page.evaluate(() => {
        const records = (window as Window & {
          __terminalInputEchoRecords?: Array<{ echoDelayMs?: number }>;
        }).__terminalInputEchoRecords ?? [];
        return records.filter((record) => typeof record.echoDelayMs === "number").length;
      }),
      { timeout: 2000 },
    ).toBe(1);

    const record = await page.evaluate(() => {
      const records = (window as Window & {
        __terminalInputEchoRecords?: Array<{
          dispatchDelayMs?: number;
          interactiveDelayMs?: number;
          writeAfterInteractiveMs?: number;
          echoDelayMs?: number;
        }>;
      }).__terminalInputEchoRecords ?? [];
      return records[0] ?? null;
    });
    s.expect(record).not.toBeNull();
    s.expect(record?.dispatchDelayMs).toBeLessThan(10);
    s.expect(record?.interactiveDelayMs).toBeLessThan(25);
    s.expect(record?.writeAfterInteractiveMs).toBeLessThan(10);
    s.expect(record?.echoDelayMs).toBeLessThan(35);
  });
});
