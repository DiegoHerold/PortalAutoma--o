"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, X } from "lucide-react";

import { NAV_GROUPS } from "@/lib/navigation";
import { cn } from "@/lib/utils";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 items-center gap-2.5 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Boxes className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <p className="font-display text-sm font-semibold text-white">Portal</p>
          <p className="text-[11px] uppercase tracking-[0.18em] text-sidebar-foreground/60">Automações</p>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/45">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-sidebar-accent text-white"
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-white",
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                    )}
                    <Icon className={cn("h-[18px] w-[18px]", active ? "text-primary" : "text-sidebar-foreground/60")} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-4">
        <p className="text-[11px] text-sidebar-foreground/50">Portal de Automações · Biason</p>
      </div>
    </div>
  );
}

export function AppSidebar() {
  return (
    <aside className="hidden w-[260px] shrink-0 lg:block">
      <div className="fixed inset-y-0 left-0 z-30 w-[260px] border-r border-sidebar-border">
        <SidebarContent />
      </div>
    </aside>
  );
}

export function MobileSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div className="absolute inset-0 bg-background/70 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-y-0 left-0 w-[260px] animate-fade-in shadow-xl">
        <button
          onClick={onClose}
          className="absolute right-3 top-4 z-10 rounded-md p-1 text-sidebar-foreground/70 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>
        <SidebarContent onNavigate={onClose} />
      </div>
    </div>
  );
}
