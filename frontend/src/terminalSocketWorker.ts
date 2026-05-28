import { createTerminalSocketOutputQueue } from "./terminalSocketOutputQueue";

type WorkerCommand =
  | { type: "connect"; url: string }
  | { type: "input"; data: Uint8Array }
  | { type: "json"; data: string }
  | { type: "close" }
  | { type: "output-ack" }
  | { type: "server-output-ack"; bytes?: number };

const workerScope = self as unknown as {
  postMessage: (message: unknown, transfer?: Transferable[]) => void;
};

let socket: WebSocket | null = null;
let closedByCommand = false;

const outputQueue = createTerminalSocketOutputQueue({
  post: ({ type, data }) => {
    if (typeof data === "string") {
      workerScope.postMessage({ type, data });
    } else {
      workerScope.postMessage({ type, data }, [data.buffer]);
    }
  },
});

function closeSocket(): void {
  closedByCommand = true;
  outputQueue.reset();
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
      nextSocket.send("{\"type\":\"output_ack\"}");
      workerScope.postMessage({ type: "open" });
    }
  };
  nextSocket.onmessage = (event) => {
    if (socket !== nextSocket) {
      return;
    }
    if (event.data instanceof ArrayBuffer) {
      outputQueue.queueOutput(new Uint8Array(event.data));
    } else {
      outputQueue.queueOutput(String(event.data));
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
  if (command.type === "output-ack") {
    outputQueue.ackOutput();
    return;
  }
  if (command.type === "server-output-ack") {
    if (socket?.readyState === WebSocket.OPEN) {
      const bytes = command.bytes;
      if (typeof bytes === "number" && Number.isFinite(bytes) && bytes > 0) {
        socket.send(JSON.stringify({ type: "output_ack", bytes }));
      } else {
        socket.send("{\"type\":\"output_ack\"}");
      }
    }
    return;
  }

  const current = socket;
  if (current?.readyState !== WebSocket.OPEN) {
    return;
  }
  if (command.type === "input") {
    outputQueue.markInputSent();
    current.send(command.data);
  } else {
    current.send(command.data);
  }
};
