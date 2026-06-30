import * as s from "./terminal-fit.support";

s.test.describe("terminal viewport fit", () => {
  s.test("printable fast path marks xterm user input without duplicate send", async ({ page }) => {
    await page.addInitScript(() => {
      const decoder = new TextDecoder();
      const state = {
        inputMessages: [] as string[],
        writeDelayMs: null as number | null,
        keydownAt: 0,
      };
      Object.defineProperty(window, "__terminalFastPathUserInput", {
        value: state,
        configurable: true,
      });

      window.addEventListener("keydown", (event) => {
        if (event.key === "q") {
          state.keydownAt = performance.now();
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
          if (ArrayBuffer.isView(data)) {
            state.inputMessages.push(decoder.decode(data));
          }
        }
        return originalPostMessage.call(this, message, transfer ?? []);
      };

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__?: (data: string | Uint8Array, parsedAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__ = (data, parsedAt) => {
        const text = typeof data === "string" ? data : decoder.decode(data);
        if (state.writeDelayMs === null && text.includes("q")) {
          state.writeDelayMs = parsedAt - state.keydownAt;
        }
      };
    });

    await s.mockApi(page, {
      onTerminalMessage: (message, ws) => {
        if (Buffer.isBuffer(message) && message.toString("utf8") === "q") {
          ws.send(Buffer.from("q"));
        }
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
    await s.waitForFilledTerminal(page, 0.9, 60_000, "fit-row-40");
    await page.locator(".terminal-xterm-host").click({ position: { x: 20, y: 20 } });
    await page.waitForFunction(() => document.activeElement?.classList.contains("xterm-helper-textarea"));
    await page.keyboard.type("q");

    await s.expect.poll(
      () => page.evaluate(() => {
        return (window as Window & {
          __terminalFastPathUserInput?: { writeDelayMs: number | null };
        }).__terminalFastPathUserInput?.writeDelayMs ?? null;
      }),
      { timeout: 2000 },
    ).not.toBeNull();

    const state = await page.evaluate(() => {
      return (window as Window & {
        __terminalFastPathUserInput?: { inputMessages: string[]; writeDelayMs: number | null };
      }).__terminalFastPathUserInput;
    });
    s.expect(state?.inputMessages.filter((message) => message === "q")).toHaveLength(1);
    s.expect(state?.writeDelayMs).toBeLessThan(35);
  });
  s.test("worker waits for output ack before posting another burst chunk", async ({ page }) => {
    await page.addInitScript(() => {
      const NativeWorker = window.Worker;
      const state = {
        outputCount: 0,
        outputCountBeforeFirstAck: null as number | null,
      };
      Object.defineProperty(window, "__terminalWorkerFlowControl", {
        value: state,
        configurable: true,
      });

      class InstrumentedWorker extends NativeWorker {
        private messageHandler: ((this: Worker, event: MessageEvent) => unknown) | null = null;

        constructor(scriptURL: string | URL, options?: WorkerOptions) {
          super(scriptURL, options);
          super.addEventListener("message", (event: MessageEvent) => {
            const data = event.data as { type?: unknown } | null;
            if (data?.type === "output" || data?.type === "interactive-output") {
              state.outputCount += 1;
              if (state.outputCount === 1) {
                window.setTimeout(() => {
                  state.outputCountBeforeFirstAck = state.outputCount;
                  this.messageHandler?.call(this, event);
                }, 80);
                return;
              }
            }
            this.messageHandler?.call(this, event);
          });
        }

        get onmessage(): ((this: Worker, event: MessageEvent) => unknown) | null {
          return this.messageHandler;
        }

        set onmessage(handler: ((this: Worker, event: MessageEvent) => unknown) | null) {
          this.messageHandler = handler;
        }
      }

      Object.defineProperty(window, "Worker", {
        value: InstrumentedWorker,
        configurable: true,
      });
    });

    await s.mockApi(page, {
      afterTerminalConnected: (ws) => {
        ws.send(Buffer.from("flow-control-one\r\n"));
        ws.send(Buffer.from("flow-control-two\r\n"));
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    await s.expect.poll(
      () => page.evaluate(() => {
        return (window as Window & {
          __terminalWorkerFlowControl?: { outputCountBeforeFirstAck: number | null };
        }).__terminalWorkerFlowControl?.outputCountBeforeFirstAck ?? null;
      }),
      { timeout: 3000 },
    ).toBe(1);

    await s.expect.poll(
      () => page.evaluate(() => {
        return (window as Window & {
          __terminalWorkerFlowControl?: { outputCount: number };
        }).__terminalWorkerFlowControl?.outputCount ?? 0;
      }),
      { timeout: 3000 },
    ).toBeGreaterThan(1);
  });
  s.test("browser releases worker output before terminal write callback", async ({ page }) => {
    await page.addInitScript(() => {
      const NativeWorker = window.Worker;
      const decoder = new TextDecoder();
      const marker = "worker-ack-before-write";
      const state = {
        markerOutputDelivered: false,
        markerWriteCalled: false,
        outputAckBeforeMarkerWrite: false,
      };
      Object.defineProperty(window, "__terminalWorkerAckFlow", {
        value: state,
        configurable: true,
      });

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__?: (data: string | Uint8Array, parsedAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__ = (data) => {
        const text = typeof data === "string" ? data : decoder.decode(data);
        if (text.includes(marker)) {
          state.markerWriteCalled = true;
        }
      };

      class InstrumentedWorker extends NativeWorker {
        private messageHandler: ((this: Worker, event: MessageEvent) => unknown) | null = null;

        constructor(scriptURL: string | URL, options?: WorkerOptions) {
          super(scriptURL, options);
          super.addEventListener("message", (event: MessageEvent) => {
            const data = event.data as { type?: unknown; data?: unknown } | null;
            if (data?.type === "output" || data?.type === "interactive-output") {
              const chunk = data.data;
              const text = typeof chunk === "string" ? chunk : decoder.decode(chunk as Uint8Array);
              if (text.includes(marker)) {
                state.markerOutputDelivered = true;
              }
            }
            this.messageHandler?.call(this, event);
          });
        }

        get onmessage(): ((this: Worker, event: MessageEvent) => unknown) | null {
          return this.messageHandler;
        }

        set onmessage(handler: ((this: Worker, event: MessageEvent) => unknown) | null) {
          this.messageHandler = handler;
        }
      }

      const originalPostMessage = NativeWorker.prototype.postMessage;
      InstrumentedWorker.prototype.postMessage = function postMessage(message: unknown, transfer?: Transferable[]) {
        if (
          typeof message === "object"
          && message !== null
          && "type" in message
          && (message as { type?: unknown }).type === "output-ack"
          && state.markerOutputDelivered
          && !state.markerWriteCalled
        ) {
          state.outputAckBeforeMarkerWrite = true;
        }
        return originalPostMessage.call(this, message, transfer ?? []);
      };

      Object.defineProperty(window, "Worker", {
        value: InstrumentedWorker,
        configurable: true,
      });
    });

    await s.mockApi(page, {
      afterTerminalConnected: (ws) => {
        ws.send(Buffer.from("worker-ack-before-write\r\n"));
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    await s.expect.poll(
      () => page.evaluate(() => {
        return (window as Window & {
          __terminalWorkerAckFlow?: { outputAckBeforeMarkerWrite: boolean };
        }).__terminalWorkerAckFlow?.outputAckBeforeMarkerWrite ?? false;
      }),
      { timeout: 3000 },
    ).toBe(true);
  });
  s.test("worker preserves queued output before echoed input", async ({ page }) => {
    await page.addInitScript(() => {
      const NativeWorker = window.Worker;
      const state = {
        delivered: [] as string[],
        delayingStale: false,
        delayedFirstStale: false,
        releaseDelayedStale: null as null | (() => void),
      };
      Object.defineProperty(window, "__terminalWorkerInputOrdering", {
        value: state,
        configurable: true,
      });

      class InstrumentedWorker extends NativeWorker {
        private messageHandler: ((this: Worker, event: MessageEvent) => unknown) | null = null;

        constructor(scriptURL: string | URL, options?: WorkerOptions) {
          super(scriptURL, options);
          super.addEventListener("message", (event: MessageEvent) => {
            const data = event.data as { type?: unknown; data?: unknown } | null;
            if (data?.type === "output" || data?.type === "interactive-output") {
              const chunk = data.data;
              const text = typeof chunk === "string" ? chunk : new TextDecoder().decode(chunk as Uint8Array);
              state.delivered.push(text);
              if (!state.delayedFirstStale && text.includes("stale-before-input-0")) {
                state.delayedFirstStale = true;
                state.delayingStale = true;
                state.releaseDelayedStale = () => {
                  state.delayingStale = false;
                  state.releaseDelayedStale = null;
                  this.messageHandler?.call(this, event);
                };
                return;
              }
            }
            this.messageHandler?.call(this, event);
          });
        }

        get onmessage(): ((this: Worker, event: MessageEvent) => unknown) | null {
          return this.messageHandler;
        }

        set onmessage(handler: ((this: Worker, event: MessageEvent) => unknown) | null) {
          this.messageHandler = handler;
        }
      }

      Object.defineProperty(window, "Worker", {
        value: InstrumentedWorker,
        configurable: true,
      });
    });

    let burstTimer: NodeJS.Timeout | null = null;
    await s.mockApi(page, {
      afterTerminalConnected: (ws) => {
        ws.send(Buffer.from("stale-before-input-0\r\n"));
        for (let index = 1; index < 20; index += 1) {
          ws.send(Buffer.from(`stale-before-input-${index}\r\n`));
        }
      },
      onTerminalMessage: (message, ws) => {
        if (!Buffer.isBuffer(message)) {
          return;
        }
        const text = message.toString("utf8");
        if (!text.includes("~")) {
          return;
        }
        burstTimer = setTimeout(() => {
          ws.send(Buffer.from("~"));
        }, 0);
      },
    });

    try {
      await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
      await page.waitForSelector(".xterm-rows", { timeout: 30_000 });
      await page.locator(".terminal-xterm-host").click({ position: { x: 20, y: 20 } });
      await page.waitForFunction(() => document.activeElement?.classList.contains("xterm-helper-textarea"));
      await s.expect.poll(
        () => page.evaluate(() => {
          return (window as Window & {
            __terminalWorkerInputOrdering?: { delayingStale: boolean };
          }).__terminalWorkerInputOrdering?.delayingStale ?? false;
        }),
        { timeout: 3000 },
      ).toBe(true);

      await page.keyboard.type("~");
      await page.waitForTimeout(50);
      await page.evaluate(() => {
        (window as Window & {
          __terminalWorkerInputOrdering?: { releaseDelayedStale: null | (() => void) };
        }).__terminalWorkerInputOrdering?.releaseDelayedStale?.();
      });

      await s.expect.poll(
        () => page.evaluate(() => {
          const state = (window as Window & {
            __terminalWorkerInputOrdering?: { delivered: string[] };
          }).__terminalWorkerInputOrdering;
          return state?.delivered.find((chunk) => chunk.includes("~")) ?? null;
        }),
        { timeout: 3000 },
      ).toBe("~");

      const delivered = await page.evaluate(() => {
        return (window as Window & {
          __terminalWorkerInputOrdering?: { delivered: string[] };
        }).__terminalWorkerInputOrdering?.delivered ?? [];
      });
      const joined = delivered.join("");
      const firstStaleIndex = joined.indexOf("stale-before-input-0");
      const lastStaleIndex = joined.indexOf("stale-before-input-19");
      const echoIndex = joined.indexOf("~");
      s.expect(firstStaleIndex).toBeGreaterThanOrEqual(0);
      s.expect(lastStaleIndex).toBeGreaterThan(firstStaleIndex);
      s.expect(echoIndex).toBeGreaterThan(lastStaleIndex);
    } finally {
      if (burstTimer !== null) {
        clearTimeout(burstTimer);
      }
    }
  });
  s.test("browser sends server output ack only after terminal write callback", async ({ page }) => {
    await page.addInitScript(() => {
      const NativeWorker = window.Worker;
      const state = {
        ackedBytes: [] as number[],
        serverAckBeforeWrite: false,
        serverAckCount: 0,
        writeHookCalled: false,
      };
      Object.defineProperty(window, "__terminalServerAckFlow", {
        value: state,
        configurable: true,
      });

      (window as Window & {
        __WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__?: (data: string | Uint8Array, parsedAt: number) => void;
      }).__WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__ = () => {
        state.writeHookCalled = true;
      };

      const originalPostMessage = NativeWorker.prototype.postMessage;
      NativeWorker.prototype.postMessage = function postMessage(message: unknown, transfer?: Transferable[]) {
        if (
          typeof message === "object"
          && message !== null
          && "type" in message
          && (message as { type?: unknown }).type === "server-output-ack"
        ) {
          state.serverAckCount += 1;
          const bytes = (message as { bytes?: unknown }).bytes;
          if (typeof bytes === "number") {
            state.ackedBytes.push(bytes);
          }
          if (!state.writeHookCalled) {
            state.serverAckBeforeWrite = true;
          }
        }
        return originalPostMessage.call(this, message, transfer ?? []);
      };
    });

    await s.mockApi(page, {
      afterTerminalConnected: (ws) => {
        ws.send(Buffer.from("server-ack-after-write\r\n"));
      },
    });

    await page.goto(s.terminalPath(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".xterm-rows", { timeout: 30_000 });

    await s.expect.poll(
      () => page.evaluate(() => {
        return (window as Window & {
          __terminalServerAckFlow?: { serverAckCount: number };
        }).__terminalServerAckFlow?.serverAckCount ?? 0;
      }),
      { timeout: 3000 },
    ).toBeGreaterThan(0);

    const state = await page.evaluate(() => {
      return (window as Window & {
        __terminalServerAckFlow?: {
          ackedBytes: number[];
          serverAckBeforeWrite: boolean;
          serverAckCount: number;
          writeHookCalled: boolean;
        };
      }).__terminalServerAckFlow;
    });
    s.expect(state?.writeHookCalled).toBe(true);
    s.expect(state?.serverAckBeforeWrite).toBe(false);
    s.expect(state?.ackedBytes.some((bytes) => bytes > 0)).toBe(true);
  });
});
