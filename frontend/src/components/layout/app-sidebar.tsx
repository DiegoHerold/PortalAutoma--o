"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

import { CONFIGURACOES, NAV_GROUPS, type NavItem } from "@/lib/navigation";
import { completar, itensEmOrdem, mover, salvarOrdem, useMenuOrdem, useMenuVisivel, type OrdemDoMenu } from "@/lib/menu";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { hasPermission, itemVisivel } from "@/lib/permissions";

const COLLAPSE_STORAGE_KEY = "portal.sidebar.collapsed";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function isItemVisible(item: NavItem, user: Parameters<typeof hasPermission>[0]): boolean {
  return itemVisivel(item, user);
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

/** Largura do "B" dentro da imagem do logo (medida no PNG: 15,9% da largura). */
const LOGO_REM = 2.25;  // altura do logo
const LOGO_LARGURA_REM = (LOGO_REM * 440) / 140;
const B_LARGURA_REM = LOGO_LARGURA_REM * 0.1591 + 0.05;
const B_CORTE_BAIXO = 25;  // % de baixo escondido no recolhido: o B vai até a linha 96 de 140

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
  const ordemSalva = useMenuOrdem();
  // Enquanto arrasta, a ordem muda na tela; só grava ao soltar.
  const [rascunho, setRascunho] = useState<OrdemDoMenu | null>(null);
  const [arrastando, setArrastando] = useState<string | null>(null);
  const ordem = completar(rascunho ?? ordemSalva);
  // Uma lista só (12/11/2026): sem títulos de categoria, na ordem que a pessoa escolheu.
  const itens = itensEmOrdem(NAV_GROUPS.flatMap((g) => g.items), ordem)
    .filter((item) => isItemVisible(item, user) && (visivel(item) || isActive(pathname, item.href)));
  const configuracoes = isItemVisible(CONFIGURACOES, user) ? CONFIGURACOES : null;

  function sobreItem(e: React.DragEvent, href: string) {
    if (!arrastando) return;
    e.preventDefault();
    if (arrastando !== href) setRascunho({ ...ordem, itens: mover(ordem.itens, arrastando, href), plana: true });
  }
  function soltar() {
    if (rascunho) salvarOrdem(rascunho);
    setRascunho(null);
    setArrastando(null);
  }
  /** Alt+↑ / Alt+↓ no item focado: mesma coisa que arrastar, pelo teclado. */
  function teclaNoItem(e: React.KeyboardEvent, href: string) {
    if (!e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    const i = itens.findIndex((x) => x.href === href);
    const vizinho = itens[e.key === "ArrowUp" ? i - 1 : i + 1];
    if (vizinho) salvarOrdem({ ...ordem, itens: mover(ordem.itens, href, vizinho.href), plana: true });
  }

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="relative border-b-[3px] border-sidebar-primary/70">
        {/* O "B" fica parado: recolhido, a mesma imagem é cortada na largura dele. */}
        <Link href="/dashboard" onClick={onNavigate} className="block px-6 py-3.5" aria-label="Biason, ir para o Painel">
          <span className="block overflow-hidden transition-[width] duration-150"
            style={{ width: `${collapsed ? B_LARGURA_REM : LOGO_LARGURA_REM}rem`, height: `${LOGO_REM}rem` }} data-testid="logo-menu">
            <Image src="/marca/logo-biason-branco.png" alt="Biason" width={440} height={140} priority
              className="max-w-none transition-[clip-path] duration-150"
              style={{ height: `${LOGO_REM}rem`, width: `${LOGO_LARGURA_REM}rem`,
                // recolhido: some também o "ASSESSORIA" que fica sob o B (linhas 112-139 de 140 no PNG)
                clipPath: collapsed ? `inset(0 0 ${B_CORTE_BAIXO}% 0)` : "inset(0 0 0 0)" }} />
          </span>
        </Link>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="absolute right-0 top-1/2 z-10 hidden h-8 w-8 translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-sidebar-primary/70 bg-nevoa text-sidebar shadow-md transition-colors hover:bg-nevoa/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sidebar-primary lg:flex"
            aria-label={collapsed ? "Expandir navegação" : "Recolher navegação"}
            title={collapsed ? "Expandir" : "Recolher"}
          >
            {collapsed ? <ChevronRight className="h-5 w-5" strokeWidth={2.5} /> : <ChevronLeft className="h-5 w-5" strokeWidth={2.5} />}
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden px-3 py-3" aria-label="Menu" data-testid="menu-itens">
        {itens.map((item) => (
          <div
            key={item.href}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = "move";
              e.dataTransfer.setData("text/plain", item.href);
              setArrastando(item.href);
            }}
            onDragOver={(e) => sobreItem(e, item.href)}
            onDrop={soltar}
            onDragEnd={soltar}
            onKeyDown={(e) => teclaNoItem(e, item.href)}
            data-item-menu={item.href}
            title={collapsed ? undefined : "Arraste para mudar a ordem"}
            className={cn("rounded-md", arrastando === item.href && "opacity-50 ring-1 ring-sidebar-primary/60")}
          >
            <ItemDoMenu item={item} ativo={isActive(pathname, item.href)} collapsed={collapsed} onNavigate={onNavigate} />
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border px-3 py-2.5">
        {configuracoes && (
          <div className="min-w-0">
            <ItemDoMenu item={configuracoes} ativo={isActive(pathname, configuracoes.href)} collapsed={collapsed} onNavigate={onNavigate} />
          </div>
        )}
      </div>
    </div>
  );
}

/** Aberto ou recolhido, o ícone tem o mesmo tamanho e fica no mesmo lugar: só o nome some. */
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
        "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        ativo ? "bg-sidebar-accent text-white" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-white",
      )}
    >
      {ativo && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-sidebar-primary" />}
      <Icon
        strokeWidth={2.25}
        className={cn("h-6 w-6 shrink-0", ativo ? "text-sidebar-primary" : "text-sidebar-foreground group-hover:text-white")}
      />
      <span className={cn("flex-1 truncate whitespace-nowrap", collapsed && "sr-only")}>{item.label}</span>
    </Link>
  );
}

export function AppSidebar() {
  const { collapsed, toggle } = useCollapsed();

  return (
    <aside className={cn("hidden shrink-0 lg:block", collapsed ? "w-[4.5rem]" : "w-[16.5rem]")}>
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 border-r border-sidebar-border transition-[width] duration-150",
          collapsed ? "w-[4.5rem]" : "w-[16.5rem]",
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
