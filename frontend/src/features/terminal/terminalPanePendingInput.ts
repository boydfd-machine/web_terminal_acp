import type { MutableRefObject } from "react";

import { PENDING_INPUT_QUEUE_MAX_SIZE } from "./terminalPaneConstants";
import type { TerminalConnectionStatus } from "./TerminalPaneTypes";

type PendingInputSessionArgs = {
  connectionStatusRef: MutableRefObject<TerminalConnectionStatus>;
  socketOpenRef: MutableRefObject<boolean>;
  socketWorkerRef: MutableRefObject<Worker | null>;
  claimCurrentTerminalView: () => void;
  reconcileViewPriority: () => void;
};

export function createPendingInputSession({
  connectionStatusRef,
  socketOpenRef,
  socketWorkerRef,
  claimCurrentTerminalView,
  reconcileViewPriority,
}: PendingInputSessionArgs) {
  const inputEncoder = new TextEncoder();
  const pendingInputs: string[] = [];

  const sendInputNow = (data: string) => {
    const worker = socketWorkerRef.current;
    if (worker === null || !socketOpenRef.current || connectionStatusRef.current !== "connected") {
      return false;
    }

    const encoded = inputEncoder.encode(data);
    worker.postMessage({ type: "input", data: encoded }, [encoded.buffer]);
    return true;
  };

  const flushPendingInputs = () => {
    while (pendingInputs.length > 0) {
      const nextInput = pendingInputs[0];
      if (!sendInputNow(nextInput)) {
        return;
      }
      pendingInputs.shift();
    }
  };

  const sendOrQueueInput = (data: string) => {
    if (sendInputNow(data)) {
      return;
    }
    pendingInputs.push(data);
    while (pendingInputs.length > PENDING_INPUT_QUEUE_MAX_SIZE) {
      pendingInputs.shift();
    }
    claimCurrentTerminalView();
    reconcileViewPriority();
  };

  return {
    flushPendingInputs,
    sendOrQueueInput,
  };
}
