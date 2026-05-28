type TerminalOutputChunk = string | Uint8Array;
type TerminalOutputWriteCallback = () => void;

type TerminalOutputItem = {
  chunk: TerminalOutputChunk;
  onWrite?: TerminalOutputWriteCallback;
};

type TerminalOutputBufferOptions = {
  write: (data: TerminalOutputChunk, onWrite?: TerminalOutputWriteCallback) => void;
  schedule?: (callback: () => void, delayMs?: number) => number;
  cancel?: (handle: number) => void;
  maxFlushCharacters?: number;
  shouldYieldToInput?: () => boolean;
  isLowPriority?: () => boolean;
  inputYieldDelayMs?: number;
  lowPriorityFlushDelayMs?: number;
  lowPriorityMaxFlushCharacters?: number;
};

type EnqueueOptions = {
  onWrite?: TerminalOutputWriteCallback;
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

  return [chunk.subarray(0, length), chunk.subarray(length)];
}

function joinItems(items: TerminalOutputItem[]): TerminalOutputItem[] {
  const joined: TerminalOutputItem[] = [];
  let stringParts: string[] = [];
  let stringCallbacks: TerminalOutputWriteCallback[] = [];
  let byteParts: Uint8Array[] = [];
  let byteCallbacks: TerminalOutputWriteCallback[] = [];

  const flushStrings = () => {
    if (stringParts.length > 0) {
      joined.push({ chunk: stringParts.join(""), onWrite: joinCallbacks(stringCallbacks) });
      stringParts = [];
      stringCallbacks = [];
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
    joined.push({ chunk: merged, onWrite: joinCallbacks(byteCallbacks) });
    byteParts = [];
    byteCallbacks = [];
  };

  for (const item of items) {
    if (typeof item.chunk === "string") {
      flushBytes();
      stringParts.push(item.chunk);
      if (item.onWrite !== undefined) {
        stringCallbacks.push(item.onWrite);
      }
    } else {
      flushStrings();
      byteParts.push(item.chunk);
      if (item.onWrite !== undefined) {
        byteCallbacks.push(item.onWrite);
      }
    }
  }
  flushStrings();
  flushBytes();
  return joined;
}

function joinCallbacks(callbacks: TerminalOutputWriteCallback[]): TerminalOutputWriteCallback | undefined {
  if (callbacks.length === 0) {
    return undefined;
  }
  return () => {
    for (const callback of callbacks) {
      callback();
    }
  };
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
  const queue: TerminalOutputItem[] = [];
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
    const pending: TerminalOutputItem[] = [];
    let pendingLength = 0;
    while (queue.length > 0) {
      const next = queue[0];
      const nextLength = chunkLength(next.chunk);
      if (pending.length === 0 && nextLength > currentMaxFlushCharacters) {
        const [head, tail] = splitChunk(next.chunk, currentMaxFlushCharacters);
        queue.shift();
        if (tail !== null) {
          queue.unshift({ chunk: tail, onWrite: next.onWrite });
        }
        pending.push({ chunk: head });
        break;
      }
      if (pending.length > 0 && pendingLength + nextLength > currentMaxFlushCharacters) {
        break;
      }
      queue.shift();
      pending.push(next);
      pendingLength += nextLength;
    }

    for (const item of joinItems(pending)) {
      options.write(item.chunk, item.onWrite);
    }

    if (queue.length > 0) {
      scheduleFlush(isLowPriority() ? lowPriorityFlushDelayMs : 0);
    }
  };

  return {
    enqueue(data: TerminalOutputChunk, enqueueOptions?: EnqueueOptions): void {
      if (disposed) {
        return;
      }
      queue.push({ chunk: data, onWrite: enqueueOptions?.onWrite });
      scheduleFlush(isLowPriority() ? lowPriorityFlushDelayMs : 0);
    },
    enqueueInteractive(data: TerminalOutputChunk, interactiveOptions?: EnqueueOptions): boolean {
      if (disposed) {
        return false;
      }
      if (
        queue.length === 0
        && scheduledHandle === null
        && !isLowPriority()
        && deferredUntil <= Date.now()
        && chunkLength(data) <= maxFlushCharacters
      ) {
        options.write(data, interactiveOptions?.onWrite);
        return true;
      }
      queue.push({ chunk: data, onWrite: interactiveOptions?.onWrite });
      scheduleFlush(isLowPriority() ? lowPriorityFlushDelayMs : 0);
      return false;
    },
    deferFor(delayMs: number): void {
      if (disposed || delayMs <= 0) {
        return;
      }
      if (queue.length === 0) {
        return;
      }
      deferredUntil = Math.max(deferredUntil, Date.now() + delayMs);
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
