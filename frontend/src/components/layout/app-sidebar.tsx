"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, ChevronsLeft, ChevronsRight, X } from "lucide-react";

import { NAV_GROUPS, type NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { hasAnyPermission, hasPermission, isAdminOrManager } from "@/lib/permissions";

const COLLAPSE_STORAGE_KEY = "portal.sidebar.collapsed";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function useVisibleNavGroups() {
  const { user } = useAuth();

  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => isItemVisible(item, user)),
  })).filter((group) => group.items.length > 0);
}

function isItemVisible(item: NavItem, user: Parameters<typeof hasPermission>[0]): boolean {
  if (item.adminOnly && !isAdminOrManager(user)) return false;
  if (item.permission && !hasPermission(user, item.permission)) return false;
  if (item.anyPermission && !hasAnyPermission(user, item.anyPermission)) return false;
  return true;
}

function useCollapsed() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(COLLAPSE_STORAGE_KEY);
    if (stored === "1") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(COLLAPSE_STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return { collapsed, toggle };
}

export function SidebarContent({
  onNavigate,
  collapsed = false,
  onToggleCollapse,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  const pathname = usePathname();
  const groups = useVisibleNavGroups();

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className={cn("flex h-16 items-center gap-2.5 px-5", collapsed && "justify-center px-0")}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Boxes className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="leading-tight">
            <p className="font-display text-sm font-semibold text-white">Portal</p>
            <p className="text-[11px] uppercase tracking-[0.18em] text-sidebar-foreground/60">Automações</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {groups.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/45">
                {group.label}
              </p>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    title={collapsed ? item.label : undefined}
                    aria-label={item.label}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      collapsed && "justify-center px-0",
                      active
                        ? "bg-sidebar-accent text-white"
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-white",
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                    )}
                    <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-primary" : "text-sidebar-foreground/60")} />
                    {!collapsed && (
                      <span className="flex-1 truncate">{item.label}</span>
                    )}
                    {!collapsed && item.comingSoon && (
                      <span className="rounded-full bg-sidebar-accent/70 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sidebar-foreground/60">
                        Em breve
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {onToggleCollapse && (
        <button
          onClick={onToggleCollapse}
          className={cn(
            "hidden items-center gap-2 border-t border-sidebar-border px-4 py-3 text-xs font-medium text-sidebar-foreground/60 hover:text-white lg:flex",
            collapsed ? "justify-center" : "justify-start",
          )}
          aria-label={collapsed ? "Expandir navegação" : "Recolher navegação"}
        >
          {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          {!collapsed && "Recolher"}
        </button>
      )}

      {!collapsed && (
        <div className="border-t border-sidebar-border p-4">
          <p className="text-[11px] text-sidebar-foreground/50">Portal de Automações · Biason</p>
        </div>
      )}
    </div>
  );
}

export function AppSidebar() {
  const { collapsed, toggle } = useCollapsed();

  return (
    <aside className={cn("hidden shrink-0 lg:block", collapsed ? "w-[76px]" : "w-[260px]")}>
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 border-r border-sidebar-border transition-[width] duration-150",
          collapsed ? "w-[76px]" : "w-[260px]",
        )}
      >
        <SidebarContent collapsed={collapsed} onToggleCollapse={toggle} />
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
