declare const process: { exitCode?: number };

import { createTerminalOutputBuffer } from "../src/terminalOutputBuffer.js";

function assert(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

async function testBatchesOutputUntilScheduledFlush(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<() => void> = [];
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
  });

  writer.enqueue("a");
  writer.enqueue("b");
  writer.enqueue("c");

  assert(writes.length === 0, "output should not be written synchronously");
  assert(scheduled.length === 1, "multiple chunks should share one scheduled flush");

  scheduled.shift()?.();

  assert(writes.length === 1, "queued output should flush as one write");
  assert(writes[0] === "abc", "queued chunks should preserve ordering");
}

async function testSmallInteractiveOutputIsDeferredOutOfSocketCallback(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<() => void> = [];
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
  });

  writer.enqueue("prompt$ ");

  assert(writes.length === 0, "small output should not be written synchronously from websocket message handling");
  assert(scheduled.length === 1, "small output should schedule a deferred flush");

  scheduled.shift()?.();

  assert(writes.length === 1, "small output should flush on the scheduled turn");
  assert(writes[0] === "prompt$ ", "small interactive output should be preserved");
}

async function testYieldsBetweenLargeFlushes(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<() => void> = [];
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
    maxFlushCharacters: 4,
  });

  writer.enqueue("abc");
  writer.enqueue("def");

  scheduled.shift()?.();

  assert(writes.length === 1, "first flush should stay under the configured budget");
  assert(writes[0] === "abc", "first chunk should flush before later output");
  assert(scheduled.length === 1, "remaining output should be deferred to a later frame");

  scheduled.shift()?.();

  assert(writes.length === 2, "deferred output should flush on the next schedule");
  assert(writes[1] === "def", "deferred chunk should preserve ordering");
}

async function testOversizedChunkFlushesWithoutDroppingData(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<() => void> = [];
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
    maxFlushCharacters: 4,
  });

  writer.enqueue("abcdef");
  writer.enqueue("g");

  scheduled.shift()?.();
  scheduled.shift()?.();

  assert(writes.length === 2, "oversized chunk should be split across scheduled turns");
  assert(writes[0] === "abcd", "first oversized chunk slice should stay under the configured budget");
  assert(writes[1] === "efg", "remaining output should preserve ordering without dropping following chunks");
}

async function testOversizedByteChunkSplitsWithoutDroppingData(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<() => void> = [];
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
    maxFlushCharacters: 4,
  });

  writer.enqueue(new Uint8Array([1, 2, 3, 4, 5, 6]));

  scheduled.shift()?.();
  scheduled.shift()?.();

  assert(writes.length === 2, "oversized byte chunk should flush in slices");
  assert(writes[0] instanceof Uint8Array, "first byte write should stay binary");
  assert(writes[1] instanceof Uint8Array, "second byte write should stay binary");
  assert(
    Array.from(writes[0] as Uint8Array).join(",") === "1,2,3,4",
    "first byte slice should preserve data"
  );
  assert(
    Array.from(writes[1] as Uint8Array).join(",") === "5,6",
    "second byte slice should preserve data"
  );
}

async function testCanDeferQueuedOutputAfterUserInput(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<{ callback: () => void; delayMs: number | undefined }> = [];
  const canceled: number[] = [];
  let now = 100;
  const realDateNow = Date.now;
  Date.now = () => now;
  try {
    const writer = createTerminalOutputBuffer({
      write: (data) => writes.push(data),
      schedule: (callback, delayMs) => {
        scheduled.push({ callback, delayMs });
        return scheduled.length;
      },
      cancel: (handle) => canceled.push(handle),
    });

    writer.enqueue("agent output");
    writer.deferFor(32);

    assert(canceled.length === 1, "deferring should cancel the pending immediate flush");
    assert(scheduled.length === 2, "deferring should schedule a delayed flush");
    assert(scheduled[1].delayMs === 32, "deferred flush should wait for the input grace window");

    scheduled[1].callback();
    assert(writes.length === 0, "output should not flush before the grace window expires");

    now = 132;
    scheduled[2].callback();
    assert(writes.length === 1, "output should flush after the input grace window");
    assert(writes[0] === "agent output", "deferred output should be preserved");
  } finally {
    Date.now = realDateNow;
  }
}

async function testInputPendingYieldsWithoutWritingOutput(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<{ callback: () => void; delayMs: number | undefined }> = [];
  let inputPending = true;
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback, delayMs) => {
      scheduled.push({ callback, delayMs });
      return scheduled.length;
    },
    cancel: () => undefined,
    shouldYieldToInput: () => inputPending,
    inputYieldDelayMs: 24,
  });

  writer.enqueue("agent output");
  scheduled[0].callback();

  assert(writes.length === 0, "pending browser input should make output flushing yield");
  assert(scheduled.length === 2, "yielding should reschedule output flushing");
  assert(scheduled[1].delayMs === 24, "yielding should use the configured input delay");

  inputPending = false;
  scheduled[1].callback();
  assert(writes.length === 1, "output should flush once input is no longer pending");
}

async function testLowPriorityOutputUsesDelayedSmallFlushes(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<{ callback: () => void; delayMs: number | undefined }> = [];
  let lowPriority = true;
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback, delayMs) => {
      scheduled.push({ callback, delayMs });
      return scheduled.length;
    },
    cancel: () => undefined,
    maxFlushCharacters: 8,
    isLowPriority: () => lowPriority,
    lowPriorityFlushDelayMs: 250,
    lowPriorityMaxFlushCharacters: 4,
  });

  writer.enqueue("abcdefghij");

  assert(scheduled[0].delayMs === 250, "low-priority output should not flush immediately");
  scheduled[0].callback();

  assert(writes[0] === "abcd", "low-priority output should use the smaller flush budget");
  assert(scheduled[1].delayMs === 250, "remaining low-priority output should stay delayed");

  lowPriority = false;
  scheduled[1].callback();
  assert(writes[1] === "efghij", "active output should return to the normal flush budget");
}

async function testCanClearQueuedOutputAndCancelPendingFlush(): Promise<void> {
  const writes: Array<string | Uint8Array> = [];
  const scheduled: Array<() => void> = [];
  const canceled: number[] = [];
  const writer = createTerminalOutputBuffer({
    write: (data) => writes.push(data),
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: (handle) => canceled.push(handle),
  });

  writer.enqueue("stale background output");
  writer.clear();
  scheduled[0]?.();

  assert(canceled.length === 1, "clearing should cancel the pending flush");
  assert(writes.length === 0, "cleared output should not be written later");
}

async function run(): Promise<void> {
  await testBatchesOutputUntilScheduledFlush();
  await testSmallInteractiveOutputIsDeferredOutOfSocketCallback();
  await testYieldsBetweenLargeFlushes();
  await testOversizedChunkFlushesWithoutDroppingData();
  await testOversizedByteChunkSplitsWithoutDroppingData();
  await testCanDeferQueuedOutputAfterUserInput();
  await testInputPendingYieldsWithoutWritingOutput();
  await testLowPriorityOutputUsesDelayedSmallFlushes();
  await testCanClearQueuedOutputAndCancelPendingFlush();
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
