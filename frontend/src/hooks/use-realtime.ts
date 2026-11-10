"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";
import { API_BASE_URL } from "@/lib/constants";

export type ConnectionState = "connecting" | "online" | "offline" | "polling";

type Options<T> = {
  /** WebSocket path relative to the API host, e.g. "/ws/executions". */
  wsPath: string;
  /** Called with each parsed message from the socket. */
  onMessage?: (data: T) => void;
  /** Fallback callback invoked on the polling cadence when the socket is unavailable. */
  onPoll?: () => void;
  pollMs?: number;
  enabled?: boolean;
};

function toWsUrl(path: string): string {
  // O token vai na primeira mensagem, nunca na URL.
  return `${API_BASE_URL.replace(/^http/, "ws")}${path}`;
}

/**
 * Subscribes to the backend realtime channel (WebSocket). If the socket cannot be
 * established or drops, transparently falls back to short polling via `onPoll`.
 * Reconnects automatically with backoff.
 */
export function useRealtime<T = unknown>({
  wsPath,
  onMessage,
  onPoll,
  pollMs = 3000,
  enabled = true,
}: Options<T>) {
  const { token } = useAuth();
  const [state, setState] = useState<ConnectionState>("connecting");
  const socketRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const retryRef = useRef(0);
  const closedByUs = useRef(false);

  useEffect(() => {
    if (!enabled || !token) return;
    closedByUs.current = false;

    const startPolling = () => {
      if (pollRef.current) return;
      setState("polling");
      onPoll?.();
      pollRef.current = setInterval(() => onPoll?.(), pollMs);
    };
    const stopPolling = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      setState((s) => (s === "polling" ? s : "connecting"));
      let ws: WebSocket;
      try {
        ws = new WebSocket(toWsUrl(wsPath));
      } catch {
        startPolling();
        return;
      }
      socketRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", token }));
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data?.type === "connected") {
            retryRef.current = 0;
            stopPolling();
            setState("online");
            return;
          }
          onMessage?.(data);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onerror = () => {
        ws.close();
      };
      ws.onclose = () => {
        socketRef.current = null;
        if (closedByUs.current) return;
        // Fall back to polling immediately, then attempt to reconnect with backoff.
        startPolling();
        retryRef.current = Math.min(retryRef.current + 1, 6);
        const delay = Math.min(1000 * 2 ** retryRef.current, 20000);
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      closedByUs.current = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      stopPolling();
      socketRef.current?.close();
      socketRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsPath, token, enabled, pollMs]);

  return { state };
}
