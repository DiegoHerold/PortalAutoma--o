"use client";

import { cn } from "@/lib/utils";
import { useRealtimeStatus } from "@/components/layout/realtime-provider";
import type { ConnectionState } from "@/hooks/use-realtime";

const meta: Record<ConnectionState, { label: string; dot: string; text: string }> = {
  online: { label: "Tempo real", dot: "bg-success", text: "text-success" },
  polling: { label: "Sincronizando", dot: "bg-warning", text: "text-warning" },
  connecting: { label: "Conectando", dot: "bg-muted-foreground", text: "text-muted-foreground" },
  offline: { label: "Offline", dot: "bg-destructive", text: "text-destructive" },
};

export function RealtimeIndicator() {
  const { state } = useRealtimeStatus();
  const m = meta[state];
  return (
    <div className="hidden items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 sm:inline-flex">
      <span className={cn("h-2 w-2 rounded-full", m.dot, state !== "offline" && "animate-pulse-dot")} />
      <span className={cn("text-xs font-medium", m.text)}>{m.label}</span>
    </div>
  );
}
