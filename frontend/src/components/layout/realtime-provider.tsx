"use client";

import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

import type { ConnectionState } from "@/hooks/use-realtime";

type RealtimeContextValue = {
  state: ConnectionState;
  setState: (s: ConnectionState) => void;
};

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

/** Shares the current realtime connection state across the shell (header indicator). */
export function RealtimeStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConnectionState>("connecting");
  return <RealtimeContext.Provider value={{ state, setState }}>{children}</RealtimeContext.Provider>;
}

export function useRealtimeStatus() {
  const ctx = useContext(RealtimeContext);
  if (!ctx) return { state: "connecting" as ConnectionState, setState: () => {} };
  return ctx;
}
