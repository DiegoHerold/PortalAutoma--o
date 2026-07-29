"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Painel lateral deslizante (drawer), para configuração de nós, mappings e
 * detalhes de execução — casos em que o Modal (max-w-lg, centralizado) é
 * pequeno demais. Em telas estreitas ocupa a tela inteira (ver seção 42).
 */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  side = "right",
  widthClassName = "w-full sm:max-w-xl",
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  side?: "right" | "left";
  widthClassName?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex">
      <div className="absolute inset-0 bg-background/70 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 flex h-full flex-col border-border bg-card shadow-2xl animate-fade-in",
          side === "right" ? "ml-auto border-l" : "mr-auto border-r",
          widthClassName,
        )}
      >
        {(title || description) && (
          <div className="flex items-start justify-between gap-4 border-b border-border p-5">
            <div className="min-w-0">
              {title && <h2 className="font-display text-base font-semibold tracking-tight">{title}</h2>}
              {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
            </div>
            <button onClick={onClose} className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
              <X className="h-5 w-5" />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex items-center justify-end gap-2 border-t border-border p-4">{footer}</div>}
      </div>
    </div>
  );
}
