type WorkerCommand =
  | { type: "connect"; url: string }
  | { type: "input"; data: Uint8Array }
  | { type: "json"; data: string }
  | { type: "close" };

type OutputChunk = string | Uint8Array;

const workerScope = self as unknown as {
  postMessage: (message: unknown, transfer?: Transferable[]) => void;
};

const MAX_OUTPUT_POST_BYTES = 8 * 1024;

let socket: WebSocket | null = null;
let outputQueue: OutputChunk[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let closedByCommand = false;

function chunkLength(chunk: OutputChunk): number {
  return typeof chunk === "string" ? chunk.length : chunk.byteLength;
}

function queueOutput(chunk: OutputChunk): void {
  outputQueue.push(chunk);
  scheduleFlush();
}

function scheduleFlush(): void {
  if (flushTimer !== null) {
    return;
  }
  flushTimer = setTimeout(flushOutput, 0);
}

function postOutput(chunk: OutputChunk): void {
  if (typeof chunk === "string") {
    workerScope.postMessage({ type: "output", data: chunk });
    return;
  }

  workerScope.postMessage({ type: "output", data: chunk }, [chunk.buffer]);
}

function flushOutput(): void {
  flushTimer = null;
  if (outputQueue.length === 0) {
    return;
  }

  const first = outputQueue.shift() as OutputChunk;
  if (typeof first === "string") {
    let data = first;
    while (outputQueue.length > 0 && typeof outputQueue[0] === "string") {
      const next = outputQueue[0] as string;
      if (data.length + next.length > MAX_OUTPUT_POST_BYTES) {
        break;
      }
      outputQueue.shift();
      data += next;
    }
    postOutput(data);
  } else {
    const chunks = [first];
    let totalLength = first.byteLength;
    while (outputQueue.length > 0 && outputQueue[0] instanceof Uint8Array) {
      const next = outputQueue[0] as Uint8Array;
      if (totalLength + next.byteLength > MAX_OUTPUT_POST_BYTES) {
        break;
      }
      outputQueue.shift();
      chunks.push(next);
      totalLength += next.byteLength;
    }

    if (chunks.length === 1) {
      postOutput(first);
    } else {
      const merged = new Uint8Array(totalLength);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(chunk, offset);
        offset += chunk.byteLength;
      }
      postOutput(merged);
    }
  }

  if (outputQueue.length > 0) {
    scheduleFlush();
  }
}

function closeSocket(): void {
  closedByCommand = true;
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  outputQueue = [];
  const current = socket;
  socket = null;
  if (current !== null) {
    current.onopen = null;
    current.onmessage = null;
    current.onerror = null;
    current.onclose = null;
    current.close();
  }
}

function connect(url: string): void {
  closeSocket();
  closedByCommand = false;
  const nextSocket = new WebSocket(url);
  nextSocket.binaryType = "arraybuffer";
  socket = nextSocket;

  nextSocket.onopen = () => {
    if (socket === nextSocket) {
      workerScope.postMessage({ type: "open" });
    }
  };
  nextSocket.onmessage = (event) => {
    if (socket !== nextSocket) {
      return;
    }
    if (event.data instanceof ArrayBuffer) {
      queueOutput(new Uint8Array(event.data));
    } else {
      queueOutput(String(event.data));
    }
  };
  nextSocket.onerror = () => {
    if (socket === nextSocket) {
      workerScope.postMessage({ type: "error" });
    }
  };
  nextSocket.onclose = () => {
    if (socket !== nextSocket) {
      return;
    }
    socket = null;
    workerScope.postMessage({ type: "close", closedByCommand });
  };
}

onmessage = (event: MessageEvent<WorkerCommand>) => {
  const command = event.data;
  if (command.type === "connect") {
    connect(command.url);
    return;
  }
  if (command.type === "close") {
    closeSocket();
    return;
  }

  const current = socket;
  if (current?.readyState !== WebSocket.OPEN) {
    return;
  }
  if (command.type === "input") {
    current.send(command.data);
  } else {
    current.send(command.data);
  }
};
