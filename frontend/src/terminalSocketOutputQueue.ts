export type TerminalSocketOutputChunk = string | Uint8Array;
export type TerminalSocketOutputType = "output" | "interactive-output";

export type TerminalSocketOutputPost = {
  type: TerminalSocketOutputType;
  data: TerminalSocketOutputChunk;
};

type QueuedOutputChunk = {
  chunk: TerminalSocketOutputChunk;
  interactive: boolean;
};

type TerminalSocketOutputQueueOptions = {
  post: (message: TerminalSocketOutputPost) => void;
  schedule?: (callback: () => void, delayMs?: number) => number;
  cancel?: (handle: number) => void;
  now?: () => number;
  maxOutputPostBytes?: number;
  interactiveInputWindowMs?: number;
};

const DEFAULT_MAX_OUTPUT_POST_BYTES = 8 * 1024;
const DEFAULT_INTERACTIVE_INPUT_WINDOW_MS = 150;

function defaultSchedule(callback: () => void, delayMs = 0): number {
  return self.setTimeout(callback, delayMs);
}

function defaultCancel(handle: number): void {
  self.clearTimeout(handle);
}

function chunkLength(chunk: TerminalSocketOutputChunk): number {
  return typeof chunk === "string" ? chunk.length : chunk.byteLength;
}

export function createTerminalSocketOutputQueue(options: TerminalSocketOutputQueueOptions) {
  const outputQueue: QueuedOutputChunk[] = [];
  const schedule = options.schedule ?? defaultSchedule;
  const cancel = options.cancel ?? defaultCancel;
  const now = options.now ?? Date.now;
  const maxOutputPostBytes = Math.max(1, options.maxOutputPostBytes ?? DEFAULT_MAX_OUTPUT_POST_BYTES);
  const interactiveInputWindowMs = Math.max(
    0,
    options.interactiveInputWindowMs ?? DEFAULT_INTERACTIVE_INPUT_WINDOW_MS
  );
  let flushTimer: number | null = null;
  let lastInputSentAt = 0;
  let outputInFlight = false;

  const cancelFlush = () => {
    if (flushTimer === null) {
      return;
    }
    cancel(flushTimer);
    flushTimer = null;
  };

  const postOutput = (chunk: TerminalSocketOutputChunk, interactive = false) => {
    outputInFlight = true;
    options.post({ type: interactive ? "interactive-output" : "output", data: chunk });
  };

  const flushOutput = () => {
    flushTimer = null;
    if (outputInFlight || outputQueue.length === 0) {
      return;
    }

    const first = outputQueue.shift() as QueuedOutputChunk;
    const interactive = first.interactive;
    if (typeof first.chunk === "string") {
      let data = first.chunk;
      while (
        outputQueue.length > 0
        && outputQueue[0].interactive === interactive
        && typeof outputQueue[0].chunk === "string"
      ) {
        const next = outputQueue[0].chunk as string;
        if (data.length + next.length > maxOutputPostBytes) {
          break;
        }
        outputQueue.shift();
        data += next;
      }
      postOutput(data, interactive);
    } else {
      const chunks = [first.chunk];
      let totalLength = first.chunk.byteLength;
      while (
        outputQueue.length > 0
        && outputQueue[0].interactive === interactive
        && outputQueue[0].chunk instanceof Uint8Array
      ) {
        const next = outputQueue[0].chunk as Uint8Array;
        if (totalLength + next.byteLength > maxOutputPostBytes) {
          break;
        }
        outputQueue.shift();
        chunks.push(next);
        totalLength += next.byteLength;
      }

      if (chunks.length === 1) {
        postOutput(first.chunk, interactive);
      } else {
        const merged = new Uint8Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
          merged.set(chunk, offset);
          offset += chunk.byteLength;
        }
        postOutput(merged, interactive);
      }
    }

    if (outputQueue.length > 0) {
      scheduleFlush();
    }
  };

  const scheduleFlush = (delayMs = 0) => {
    if (flushTimer !== null || outputInFlight) {
      return;
    }
    flushTimer = schedule(flushOutput, delayMs);
  };

  return {
    markInputSent(): void {
      lastInputSentAt = now();
    },
    queueOutput(chunk: TerminalSocketOutputChunk): void {
      const interactive = now() - lastInputSentAt <= interactiveInputWindowMs;
      if (interactive && outputQueue.length === 0 && flushTimer === null && !outputInFlight) {
        postOutput(chunk, true);
        return;
      }
      outputQueue.push({ chunk, interactive });
      scheduleFlush();
    },
    ackOutput(): void {
      outputInFlight = false;
      if (outputQueue.length === 0) {
        return;
      }
      if (outputQueue[0].interactive) {
        cancelFlush();
        flushOutput();
        return;
      }
      scheduleFlush();
    },
    reset(): void {
      outputQueue.length = 0;
      outputInFlight = false;
      cancelFlush();
    },
  };
}
