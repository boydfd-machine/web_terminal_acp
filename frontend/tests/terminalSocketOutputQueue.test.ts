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

async function run(): Promise<void> {
  await testInputDoesNotDropQueuedOutput();
  await testQueuedInteractiveOutputFlushesImmediatelyAfterAck();
  await testNonInteractiveOutputStillBatchesOnTimer();
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
