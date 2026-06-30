import { useEffect } from "react";
import type { QueryClient } from "@tanstack/react-query";

import { uiEventsWebSocketUrl } from "../api";
import {
  AUTH_TOKEN_STORAGE_KEY,
  authChangedEventName,
  readAuthToken,
  webSocketAuthProtocols,
} from "../auth";
import {
  createUiInvalidationScheduler,
  nextUiEventReconnectDelay,
  parseUiEvent,
  type UiInvalidateEvent,
} from "../uiEvents";

export function useUiInvalidationSocket(queryClient: QueryClient, authEnabled = false): void {
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    const invalidationScheduler = createUiInvalidationScheduler(queryClient);
    let reconnectAttempt = 0;
    let closed = false;

    const canConnect = () => !authEnabled || readAuthToken() !== null;

    const clearReconnectTimer = () => {
      if (reconnectTimer === null) {
        return;
      }
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    };

    const closeSocket = () => {
      if (socket === null) {
        return;
      }
      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;
      socket.close();
      socket = null;
    };

    const scheduleReconnect = () => {
      if (closed || reconnectTimer !== null || !canConnect()) {
        return;
      }
      reconnectAttempt += 1;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, nextUiEventReconnectDelay(reconnectAttempt));
    };

    const handleMessage = (nextSocket: WebSocket, message: MessageEvent) => {
      if (socket !== nextSocket || typeof message.data !== "string") {
        return;
      }
      const event = parseUiEvent(message.data);
      if (event?.type !== "invalidate") {
        return;
      }

      invalidationScheduler.schedule(event);
    };

    function connect() {
      if (closed) {
        return;
      }
      if (!canConnect()) {
        closeSocket();
        return;
      }
      closeSocket();
      const protocols = webSocketAuthProtocols();
      const nextSocket = protocols.length > 0
        ? new WebSocket(uiEventsWebSocketUrl(), protocols)
        : new WebSocket(uiEventsWebSocketUrl());
      socket = nextSocket;
      nextSocket.onopen = () => {
        if (socket === nextSocket) {
          reconnectAttempt = 0;
        }
      };
      nextSocket.onmessage = (message) => handleMessage(nextSocket, message);
      nextSocket.onclose = () => {
        if (socket === nextSocket) {
          scheduleReconnect();
        }
      };
      nextSocket.onerror = () => {
        nextSocket.close();
      };
    }

    const handleAuthChanged = () => {
      clearReconnectTimer();
      reconnectAttempt = 0;
      connect();
    };
    const handleAuthStorageChanged = (event: StorageEvent) => {
      if (event.key !== AUTH_TOKEN_STORAGE_KEY) {
        return;
      }
      handleAuthChanged();
    };

    window.addEventListener(authChangedEventName(), handleAuthChanged);
    window.addEventListener("storage", handleAuthStorageChanged);
    connect();
    return () => {
      closed = true;
      window.removeEventListener(authChangedEventName(), handleAuthChanged);
      window.removeEventListener("storage", handleAuthStorageChanged);
      clearReconnectTimer();
      invalidationScheduler.dispose();
      closeSocket();
    };
  }, [authEnabled, queryClient]);
}
