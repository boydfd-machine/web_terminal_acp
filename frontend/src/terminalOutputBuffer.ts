type TerminalOutputChunk = string | Uint8Array;

type TerminalOutputBufferOptions = {
  write: (data: TerminalOutputChunk) => void;
  schedule?: (callback: () => void, delayMs?: number) => number;
  cancel?: (handle: number) => void;
  maxFlushCharacters?: number;
  shouldYieldToInput?: () => boolean;
  isLowPriority?: () => boolean;
  inputYieldDelayMs?: number;
  lowPriorityFlushDelayMs?: number;
  lowPriorityMaxFlushCharacters?: number;
};

const DEFAULT_MAX_FLUSH_CHARACTERS = 4 * 1024;
const DEFAULT_INPUT_YIELD_DELAY_MS = 16;
const DEFAULT_LOW_PRIORITY_FLUSH_DELAY_MS = 250;
const DEFAULT_LOW_PRIORITY_MAX_FLUSH_CHARACTERS = 1024;

function chunkLength(chunk: TerminalOutputChunk): number {
  return typeof chunk === "string" ? chunk.length : chunk.byteLength;
}

function splitChunk(chunk: TerminalOutputChunk, length: number): [TerminalOutputChunk, TerminalOutputChunk | null] {
  if (chunkLength(chunk) <= length) {
    return [chunk, null];
  }

  if (typeof chunk === "string") {
    return [chunk.slice(0, length), chunk.slice(length)];
  }

  return [chunk.slice(0, length), chunk.slice(length)];
}

function joinChunks(chunks: TerminalOutputChunk[]): TerminalOutputChunk[] {
  const joined: TerminalOutputChunk[] = [];
  let stringParts: string[] = [];
  let byteParts: Uint8Array[] = [];

  const flushStrings = () => {
    if (stringParts.length > 0) {
      joined.push(stringParts.join(""));
      stringParts = [];
    }
  };

  const flushBytes = () => {
    if (byteParts.length === 0) {
      return;
    }
    const totalLength = byteParts.reduce((total, chunk) => total + chunk.byteLength, 0);
    const merged = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of byteParts) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    joined.push(merged);
    byteParts = [];
  };

  for (const chunk of chunks) {
    if (typeof chunk === "string") {
      flushBytes();
      stringParts.push(chunk);
    } else {
      flushStrings();
      byteParts.push(chunk);
    }
  }
  flushStrings();
  flushBytes();
  return joined;
}

function defaultShouldYieldToInput(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }

  const scheduling = (navigator as Navigator & {
    scheduling?: {
      isInputPending?: (options?: { includeContinuous?: boolean }) => boolean;
    };
  }).scheduling;
  return scheduling?.isInputPending?.({ includeContinuous: true }) ?? false;
}

function defaultSchedule(callback: () => void, delayMs = 0): number {
  return window.setTimeout(callback, delayMs);
}

function defaultCancel(handle: number): void {
  window.clearTimeout(handle);
}

export function createTerminalOutputBuffer(options: TerminalOutputBufferOptions) {
  const queue: TerminalOutputChunk[] = [];
  const schedule = options.schedule ?? defaultSchedule;
  const cancel = options.cancel ?? defaultCancel;
  const maxFlushCharacters = Math.max(1, options.maxFlushCharacters ?? DEFAULT_MAX_FLUSH_CHARACTERS);
  const shouldYieldToInput = options.shouldYieldToInput ?? defaultShouldYieldToInput;
  const isLowPriority = options.isLowPriority ?? (() => false);
  const inputYieldDelayMs = Math.max(0, options.inputYieldDelayMs ?? DEFAULT_INPUT_YIELD_DELAY_MS);
  const lowPriorityFlushDelayMs = Math.max(
    0,
    options.lowPriorityFlushDelayMs ?? DEFAULT_LOW_PRIORITY_FLUSH_DELAY_MS
  );
  const lowPriorityMaxFlushCharacters = Math.max(
    1,
    options.lowPriorityMaxFlushCharacters ?? DEFAULT_LOW_PRIORITY_MAX_FLUSH_CHARACTERS
  );
  let scheduledHandle: number | null = null;
  let deferredUntil = 0;
  let disposed = false;

  const scheduleFlush = (delayMs = 0) => {
    if (disposed || scheduledHandle !== null) {
      return;
    }
    scheduledHandle = schedule(flush, delayMs);
  };

  const flush = () => {
    scheduledHandle = null;
    if (disposed) {
      queue.length = 0;
      return;
    }
    const now = Date.now();
    if (deferredUntil > now) {
      scheduleFlush(deferredUntil - now);
      return;
    }
    if (shouldYieldToInput()) {
      scheduleFlush(inputYieldDelayMs);
      return;
    }

    const currentMaxFlushCharacters = isLowPriority()
      ? Math.min(maxFlushCharacters, lowPriorityMaxFlushCharacters)
      : maxFlushCharacters;
    const pending: TerminalOutputChunk[] = [];
    let pendingLength = 0;
    while (queue.length > 0) {
      const next = queue[0];
      const nextLength = chunkLength(next);
      if (pending.length === 0 && nextLength > currentMaxFlushCharacters) {
        const [head, tail] = splitChunk(next, currentMaxFlushCharacters);
        queue.shift();
        if (tail !== null) {
          queue.unshift(tail);
        }
        pending.push(head);
        break;
      }
      if (pending.length > 0 && pendingLength + nextLength > currentMaxFlushCharacters) {
        break;
      }
      queue.shift();
      pending.push(next);
      pendingLength += nextLength;
    }

    for (const chunk of joinChunks(pending)) {
      options.write(chunk);
    }

    if (queue.length > 0) {
      scheduleFlush(isLowPriority() ? lowPriorityFlushDelayMs : 0);
    }
  };

  return {
    enqueue(data: TerminalOutputChunk): void {
      if (disposed) {
        return;
      }
      queue.push(data);
      scheduleFlush(isLowPriority() ? lowPriorityFlushDelayMs : 0);
    },
    deferFor(delayMs: number): void {
      if (disposed || delayMs <= 0) {
        return;
      }
      deferredUntil = Math.max(deferredUntil, Date.now() + delayMs);
      if (queue.length === 0) {
        return;
      }
      if (scheduledHandle !== null) {
        cancel(scheduledHandle);
        scheduledHandle = null;
      }
      scheduleFlush(Math.max(0, deferredUntil - Date.now()));
    },
    clear(): void {
      queue.length = 0;
      deferredUntil = 0;
      if (scheduledHandle !== null) {
        cancel(scheduledHandle);
        scheduledHandle = null;
      }
    },
    dispose(): void {
      disposed = true;
      queue.length = 0;
      if (scheduledHandle !== null) {
        cancel(scheduledHandle);
        scheduledHandle = null;
      }
    },
  };
}
