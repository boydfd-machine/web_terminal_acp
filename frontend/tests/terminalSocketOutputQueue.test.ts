declare const process: { exitCode?: number };

import { createTerminalSocketOutputQueue, type TerminalSocketOutputPost } from "../src/terminalSocketOutputQueue.js";

function assert(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function textOf(data: string | Uint8Array): string {
  return typeof data === "string" ? data : Array.from(data).join(",");
}

async function testInputDoesNotDropQueuedOutput(): Promise<void> {
  const posts: TerminalSocketOutputPost[] = [];
  const scheduled: Array<() => void> = [];
  let now = 1000;
  const queue = createTerminalSocketOutputQueue({
    post: (message) => posts.push(message),
    now: () => now,
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
  });

  queue.queueOutput("older");
  assert(scheduled.length === 1, "older output should schedule a flush");

  now = 1005;
  queue.markInputSent();

  queue.queueOutput("x");
  assert(posts.length === 0, "input must not let newer echo bypass queued output");

  scheduled[0]();
  assert(posts.length === 1, "queued output should flush on schedule");
  assert(posts[0].type === "output", "queued older output keeps normal priority");
  assert(textOf(posts[0].data) === "older", "older output must flush before later echo");

  queue.ackOutput();
  assert(posts.length === 2, "echo after input should flush after older output is acknowledged");
  assert(posts[1].type === "interactive-output", "echo after input should keep interactive priority");
  assert(textOf(posts[1].data) === "x", "echo output should be preserved");
}

async function testQueuedInteractiveOutputFlushesImmediatelyAfterAck(): Promise<void> {
  const posts: TerminalSocketOutputPost[] = [];
  const scheduled: Array<() => void> = [];
  let now = 2000;
  const queue = createTerminalSocketOutputQueue({
    post: (message) => posts.push(message),
    now: () => now,
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
  });

  queue.markInputSent();
  queue.queueOutput("a");
  assert(posts.length === 1, "first echo should post immediately");
  assert(posts[0].type === "interactive-output", "first echo should be interactive");

  now = 2010;
  queue.queueOutput("b");
  assert(posts.length === 1, "second echo should wait while output is in flight");

  queue.ackOutput();
  assert(posts.length === 2, "interactive echo should flush in the ack turn");
  assert(posts[1].type === "interactive-output", "queued echo should keep interactive priority");
  assert(textOf(posts[1].data) === "b", "queued echo should be preserved");
  assert(scheduled.length === 0, "queued interactive echo should not wait for a timer after ack");
}

async function testNonInteractiveOutputStillBatchesOnTimer(): Promise<void> {
  const posts: TerminalSocketOutputPost[] = [];
  const scheduled: Array<() => void> = [];
  const queue = createTerminalSocketOutputQueue({
    post: (message) => posts.push(message),
    now: () => 5000,
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
  });

  queue.queueOutput("a");
  queue.queueOutput("b");
  assert(posts.length === 0, "background output should wait for the scheduled flush");
  assert(scheduled.length === 1, "background output should share one scheduled flush");

  scheduled[0]();
  assert(posts.length === 1, "background output should flush on schedule");
  assert(posts[0].type === "output", "background output should not be marked interactive");
  assert(textOf(posts[0].data) === "ab", "background output should batch adjacent strings");
}

async function testControlMessagesDoNotMergeWithEachOtherOrOutput(): Promise<void> {
  const posts: TerminalSocketOutputPost[] = [];
  const scheduled: Array<() => void> = [];
  const queue = createTerminalSocketOutputQueue({
    post: (message) => posts.push(message),
    now: () => 6000,
    schedule: (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancel: () => undefined,
  });

  queue.queueOutput("a");
  queue.queueControl("{\"type\":\"terminal_selection\",\"window_id\":\"w1\"}");
  queue.queueControl("{\"type\":\"terminal_selection\",\"window_id\":\"w2\"}");
  queue.queueOutput("b");
  scheduled[0]();

  assert(posts.length === 1, "first output should flush first");
  assert(posts[0].type === "output", "normal terminal output should remain output");
  assert(textOf(posts[0].data) === "a", "output before controls should be preserved");

  queue.ackOutput();
  assert(posts.length === 2, "first control should flush after output ack");
  assert(posts[1].type === "control", "control should stay out of terminal output");
  assert(textOf(posts[1].data).includes("\"w1\""), "first control should not merge with the second");

  queue.ackOutput();
  assert(posts.length === 3, "second control should flush as its own frame");
  assert(posts[2].type === "control", "second control should stay out of terminal output");
  assert(textOf(posts[2].data).includes("\"w2\""), "second control should be preserved");

  queue.ackOutput();
  assert(posts.length === 3, "normal output after controls should still wait for its scheduled flush");
  scheduled[1]();
  assert(posts.length === 4, "output after controls should flush last");
  assert(posts[3].type === "output", "trailing terminal output should remain output");
  assert(textOf(posts[3].data) === "b", "trailing output should be preserved");
}

async function run(): Promise<void> {
  await testInputDoesNotDropQueuedOutput();
  await testQueuedInteractiveOutputFlushesImmediatelyAfterAck();
  await testNonInteractiveOutputStillBatchesOnTimer();
  await testControlMessagesDoNotMergeWithEachOtherOrOutput();
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
