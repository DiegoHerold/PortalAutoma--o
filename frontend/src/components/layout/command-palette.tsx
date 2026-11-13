"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, CornerDownLeft } from "lucide-react";

import { Portal } from "@/components/ui/portal";
import { ALL_NAV_ITEMS } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { itemVisivel } from "@/lib/permissions";

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const visibleItems = useMemo(
    () =>
      ALL_NAV_ITEMS.filter((item) => itemVisivel(item, user)),
    [user],
  );

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return visibleItems;
    return visibleItems.filter((i) => i.label.toLowerCase().includes(q));
  }, [query, visibleItems]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(a + 1, results.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(a - 1, 0));
      }
      if (e.key === "Enter" && results[active]) {
        router.push(results[active].href);
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, results, active, router, onClose]);

  if (!open) return null;

  return (
    <Portal>
    <div className="fixed inset-0 z-[95] flex items-start justify-center px-4 pt-[12vh]">
      <div className="absolute inset-0 bg-background/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-xl animate-fade-in overflow-hidden rounded-xl border border-border bg-popover shadow-2xl">
        <div className="flex items-center gap-2 border-b border-border px-4">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            placeholder="Buscar telas e ações…"
            className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">ESC</kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {results.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">Nenhum resultado</p>
          )}
          {results.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                key={item.href}
                onMouseEnter={() => setActive(index)}
                onClick={() => {
                  router.push(item.href);
                  onClose();
                }}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm",
                  index === active ? "bg-accent text-accent-foreground" : "text-foreground",
                )}
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1">{item.label}</span>
                {index === active && <CornerDownLeft className="h-3.5 w-3.5 text-muted-foreground" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
    </Portal>
  );
}
