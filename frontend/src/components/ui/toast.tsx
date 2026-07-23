"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import { CheckCircle2, Info, X, AlertTriangle, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

type ToastKind = "success" | "error" | "info" | "warning";
type Toast = { id: number; title: string; description?: string; kind: ToastKind };

type ToastContextValue = {
  toast: (t: { title: string; description?: string; kind?: ToastKind }) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const icons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
} as const;

const accents: Record<ToastKind, string> = {
  success: "text-success",
  error: "text-destructive",
  info: "text-info",
  warning: "text-warning",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => setToasts((prev) => prev.filter((t) => t.id !== id)), []);

  const toast = useCallback<ToastContextValue["toast"]>(
    ({ title, description, kind = "info" }) => {
      const id = Date.now() + Math.random();
      setToasts((prev) => [...prev, { id, title, description, kind }]);
      setTimeout(() => remove(id), 4200);
    },
    [remove],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
        {toasts.map((t) => {
          const Icon = icons[t.kind];
          return (
            <div
              key={t.id}
              className="pointer-events-auto flex animate-fade-in items-start gap-3 rounded-lg border border-border bg-popover p-3.5 text-popover-foreground shadow-lg"
            >
              <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", accents[t.kind])} />
              <div className="flex-1">
                <p className="text-sm font-medium">{t.title}</p>
                {t.description && <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>}
              </div>
              <button onClick={() => remove(t.id)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) return { toast: () => {} };
  return ctx;
}
