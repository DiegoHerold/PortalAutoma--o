"use client";

import Link from "next/link";
import { ArrowUpRight, GripVertical, RotateCcw } from "lucide-react";

import { useAuth } from "@/hooks/use-auth";
import { aplicarOrdem, restaurarMenu, salvarMenu, useMenuItens, useMenuOrdem } from "@/lib/menu";
import { NAV_GROUPS, type NavItem } from "@/lib/navigation";
import { itemVisivel } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/** Uma frase do que cada área faz: quem abre as Configurações sabe para onde vai. */
const DESCRICOES: Record<string, string> = {
  "/dashboard": "Telas ao vivo, progresso e estimativas do que está rodando.",
  "/fila": "O que espera, em qual máquina e quando começa.",
  "/maquinas": "Linha do tempo por máquina e automações diretas.",
  "/historico": "Execuções terminadas e tempos por item.",
  "/executions": "Detalhes técnicos de cada execução.",
  "/flows": "Programas em blocos que encadeiam automações (em reconstrução).",
  "/webhooks": "Gatilhos chamados por outros sistemas.",
  "/schedules": "Execuções com dia e hora marcados.",
  "/automations": "Cadastro das automações, versões e itens.",
  "/categories": "Agrupamento das automações e permissões.",
  "/runtimes": "Ambientes que o Agent usa para rodar pacotes.",
  "/workers": "Agents instalados nas máquinas.",
  "/storage": "Arquivos guardados pelo portal.",
  "/audit": "Quem fez o quê, e quando.",
  "/secrets": "Senhas e chaves usadas pelas automações.",
  "/service-accounts": "Acessos de sistemas que falam com o portal.",
  "/users": "Pessoas com acesso ao portal.",
  "/teams": "Grupos de pessoas para dar acesso junto.",
  "/roles": "O que cada papel pode fazer.",
  "/organizations": "Contextos administrativos.",
  "/governance/limits": "Limites de uso do sistema.",
  "/governance/retention": "Por quanto tempo guardar imagens e logs.",
  "/pendencias": "Itens esperando uma pessoa e o botão para continuar o processo.",
  "/emails": "O que o Portal enviou por e-mail e para quais domínios as automações podem mandar.",
};

export function podeVer(item: NavItem, user: Parameters<typeof itemVisivel>[1]): boolean {
  return itemVisivel(item, user);
}

/**
 * Todas as áreas do portal que a pessoa pode abrir, por categoria e na mesma ordem do menu.
 * Cada uma tem o atalho para abrir e a chave "no menu": nada fica sem caminho, esteja ou
 * não no menu lateral.
 */
export function AreasDoPortal() {
  const { user } = useAuth();
  const noMenu = useMenuItens();
  const ordem = useMenuOrdem();
  const categorias = aplicarOrdem(NAV_GROUPS, ordem)
    .map((g) => ({ ...g, items: g.items.filter((i) => podeVer(i, user)) }))
    .filter((g) => g.items.length > 0);
  const total = categorias.reduce((n, g) => n + g.items.length, 0);
  const ligados = categorias.reduce((n, g) => n + g.items.filter((i) => noMenu.has(i.href)).length, 0);

  function alternar(href: string, ligado: boolean) {
    const novo = new Set(noMenu);
    if (ligado) novo.add(href);
    else novo.delete(href);
    salvarMenu(novo);
  }

  return (
    <section className="space-y-5" data-testid="areas-do-portal">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="titulo-condensado text-2xl">Menu e atalhos</h2>
          <p className="max-w-2xl text-muted-foreground">
            Tudo o que você pode abrir no portal. Ligue o que quer à mão no menu lateral; o resto continua aqui.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{ligados} de {total} no menu</span>
          <Button variant="outline" onClick={restaurarMenu}>
            <RotateCcw className="h-4 w-4" /> Restaurar padrão
          </Button>
        </div>
      </div>
      <p className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
        <GripVertical className="h-4 w-4 shrink-0" />
        Para mudar a ordem, arraste os itens ou o nome da categoria no próprio menu (ou Alt+↑/↓ no item). Vale para este navegador.
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        {categorias.map((g) => (
          <div key={g.label} className="overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-categoria={g.label}>
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h3 className="eyebrow">{g.label}</h3>
              <span className="text-xs text-muted-foreground">
                {g.items.filter((i) => noMenu.has(i.href)).length} de {g.items.length} no menu
              </span>
            </div>
            <ul className="divide-y divide-border">
              {g.items.map((item) => {
                const Icon = item.icon;
                const ligado = noMenu.has(item.href);
                return (
                  <li key={item.href} className="flex items-center gap-4 px-5 py-3">
                    <Icon className={cn("h-5 w-5 shrink-0", ligado ? "text-primary" : "text-muted-foreground")} />
                    <div className="min-w-0 flex-1">
                      <Link href={item.href} className="group inline-flex items-center gap-1 font-medium text-titulo hover:underline">
                        {item.label}
                        <ArrowUpRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                      </Link>
                      {DESCRICOES[item.href] && <p className="text-sm text-muted-foreground">{DESCRICOES[item.href]}</p>}
                    </div>
                    <label className="flex shrink-0 cursor-pointer items-center gap-2 text-sm">
                      <span className={ligado ? "font-medium text-titulo" : "text-muted-foreground"}>{ligado ? "No menu" : "Fora do menu"}</span>
                      <input type="checkbox" className="h-5 w-5 cursor-pointer accent-[hsl(var(--primary))]" checked={ligado}
                        onChange={(e) => alternar(item.href, e.target.checked)} aria-label={`Mostrar ${item.label} no menu`} />
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
