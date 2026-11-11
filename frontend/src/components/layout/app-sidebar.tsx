"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsLeft, ChevronsRight, X } from "lucide-react";

import { CONFIGURACOES, NAV_GROUPS, type NavItem } from "@/lib/navigation";
import { aplicarOrdem, completar, mover, salvarOrdem, useMenuOrdem, useMenuVisivel, type OrdemDoMenu } from "@/lib/menu";
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
  const { user } = useAuth();
  const visivel = useMenuVisivel();
  // Categorias com os itens que a pessoa pode ver e escolheu mostrar (Configurações > Menu lateral).
  const ordemSalva = useMenuOrdem();
  // Enquanto arrasta, a ordem muda na tela; só grava ao soltar.
  const [rascunho, setRascunho] = useState<OrdemDoMenu | null>(null);
  const [arrastando, setArrastando] = useState<{ tipo: "item"; href: string; grupo: string } | { tipo: "grupo"; label: string } | null>(null);
  const ordem = completar(rascunho ?? ordemSalva);
  const groups = aplicarOrdem(useVisibleNavGroups(), ordem)
    .map((g) => ({ ...g, items: g.items.filter((item) => visivel(item) || isActive(pathname, item.href)) }))
    .filter((g) => g.items.length > 0);
  const configuracoes = isItemVisible(CONFIGURACOES, user) ? CONFIGURACOES : null;

  function sobreItem(e: React.DragEvent, grupo: string, href: string) {
    if (arrastando?.tipo === "item" && arrastando.grupo === grupo) {
      e.preventDefault();
      if (arrastando.href !== href) setRascunho({ ...ordem, itens: mover(ordem.itens, arrastando.href, href) });
    }
  }
  function sobreGrupo(e: React.DragEvent, label: string) {
    if (arrastando?.tipo === "grupo") {
      e.preventDefault();
      if (arrastando.label !== label) setRascunho({ ...ordem, grupos: mover(ordem.grupos, arrastando.label, label) });
    }
  }
  function soltar() {
    if (rascunho) salvarOrdem(rascunho);
    setRascunho(null);
    setArrastando(null);
  }
  /** Alt+↑ / Alt+↓ no item focado: mesma coisa que arrastar, pelo teclado. */
  function teclaNoItem(e: React.KeyboardEvent, grupo: { items: NavItem[] }, href: string) {
    if (!e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    const i = grupo.items.findIndex((x) => x.href === href);
    const vizinho = grupo.items[e.key === "ArrowUp" ? i - 1 : i + 1];
    if (vizinho) salvarOrdem({ ...ordem, itens: mover(ordem.itens, href, vizinho.href) });
  }

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <Link
        href="/dashboard"
        onClick={onNavigate}
        className={cn("block border-b-[3px] border-sidebar-primary/70 px-5 py-3", collapsed && "flex justify-center px-0")}
        aria-label="Biason, ir para o Painel"
      >
        {collapsed ? (
          <span className="titulo-condensado flex h-10 w-10 items-center justify-center rounded-md bg-sidebar-accent text-xl text-white">B</span>
        ) : (
          <Image src="/marca/logo-biason-branco.png" alt="Biason" width={110} height={35} priority className="h-9 w-auto" />
        )}
      </Link>

      <nav className={cn("flex-1 overflow-y-auto px-3 py-3", collapsed ? "space-y-2" : "space-y-3")}>
        {groups.map((group) => (
          <div key={group.label} onDragOver={(e) => sobreGrupo(e, group.label)} onDrop={soltar} data-grupo={group.label}
            className={cn("rounded-md", arrastando?.tipo === "grupo" && arrastando.label === group.label && "bg-sidebar-accent/40")}>
            {!collapsed && (
              <p
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "move";
                  e.dataTransfer.setData("text/plain", group.label);
                  setArrastando({ tipo: "grupo", label: group.label });
                }}
                onDragEnd={soltar}
                title="Arraste para mudar a ordem das categorias"
                className="cursor-grab select-none px-3 pb-1 text-xs font-bold uppercase tracking-[0.16em] text-sidebar-primary/60 active:cursor-grabbing"
              >
                {group.label}
              </p>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <div
                  key={item.href}
                  draggable
                  onDragStart={(e) => {
                    e.stopPropagation();
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", item.href);
                    setArrastando({ tipo: "item", href: item.href, grupo: group.label });
                  }}
                  onDragOver={(e) => sobreItem(e, group.label, item.href)}
                  onDragEnd={soltar}
                  onKeyDown={(e) => teclaNoItem(e, group, item.href)}
                  data-item-menu={item.href}
                  className={cn("rounded-md", arrastando?.tipo === "item" && arrastando.href === item.href && "opacity-50 ring-1 ring-sidebar-primary/60")}
                >
                  <ItemDoMenu item={item} ativo={isActive(pathname, item.href)} collapsed={collapsed} onNavigate={onNavigate} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className={cn("flex gap-1 border-t border-sidebar-border px-3 py-2.5", collapsed && "flex-col")}>
        {configuracoes && (
          <div className="min-w-0 flex-1">
            <ItemDoMenu item={configuracoes} ativo={isActive(pathname, configuracoes.href)} collapsed={collapsed} onNavigate={onNavigate} />
          </div>
        )}
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="hidden h-9 w-9 shrink-0 items-center justify-center self-center rounded-md text-sidebar-foreground/60 hover:bg-sidebar-accent/60 hover:text-white lg:flex"
            aria-label={collapsed ? "Expandir navegação" : "Recolher navegação"}
            title={collapsed ? "Expandir" : "Recolher"}
          >
            {collapsed ? <ChevronsRight className="h-5 w-5" /> : <ChevronsLeft className="h-4 w-4" />}
          </button>
        )}
      </div>
    </div>
  );
}

function ItemDoMenu({ item, ativo, collapsed, onNavigate }: { item: NavItem; ativo: boolean; collapsed: boolean; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      draggable={false}
      title={collapsed ? item.label : undefined}
      aria-label={item.label}
      className={cn(
        "group relative flex items-center gap-3 rounded-md px-3 py-1.5 text-[0.9375rem] font-medium transition-colors",
        collapsed && "justify-center px-0 py-1.5",
        ativo ? "bg-sidebar-accent text-white" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-white",
      )}
    >
      {ativo && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-sidebar-primary" />}
      <Icon className={cn("shrink-0", collapsed ? "h-[1.65rem] w-[1.65rem]" : "h-[18px] w-[18px]", ativo ? "text-sidebar-primary" : "text-sidebar-foreground/70")} />
      {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
    </Link>
  );
}

export function AppSidebar() {
  const { collapsed, toggle } = useCollapsed();

  return (
    <aside className={cn("hidden shrink-0 lg:block", collapsed ? "w-[4.75rem]" : "w-[16.5rem]")}>
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 border-r border-sidebar-border transition-[width] duration-150",
          collapsed ? "w-[4.75rem]" : "w-[16.5rem]",
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
      <div className="absolute inset-y-0 left-0 w-[16.5rem] animate-fade-in shadow-xl">
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
