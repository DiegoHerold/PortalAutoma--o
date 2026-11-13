import Link from "next/link";
import { Archive, Pencil, Play } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SITUACOES } from "@/lib/acompanhar";
import { relativo } from "@/lib/fila";
import type { Automation } from "@/types/automation";

/*
 * Cartão do Catálogo (12/11/2026): o que importa para USAR a automação — nome, categoria, se está
 * rodando ou na fila, a descrição, a última execução e o botão Executar. Os detalhes técnicos
 * (executor, prioridade, tempo limite, slug, pacote) ficam na aba Técnico da automação.
 */

export type UltimaExecucao = { execucao_id: string; status: string; quando: string | null };

export function AutomationCard({
  automation,
  categoryName,
  rodando = 0,
  naFila = 0,
  ultima,
  onExecutar,
  onEdit,
  onDelete,
  onRestore,
}: {
  automation: Automation;
  categoryName?: string;
  /** Execuções desta automação rodando agora (do Painel). */
  rodando?: number;
  /** Jobs desta automação esperando na Fila. */
  naFila?: number;
  ultima?: UltimaExecucao | null;
  /** Só aparece para quem pode executar. */
  onExecutar?: (automation: Automation) => void;
  onEdit?: (automation: Automation) => void;
  onDelete?: (automation: Automation) => void;
  onRestore?: (automation: Automation) => void;
}) {
  const arquivada = automation.status === "archived";
  const situacao = ultima ? SITUACOES[ultima.status] ?? { texto: ultima.status, tom: "neutral" as const } : null;
  const parar = (e: React.MouseEvent) => { e.preventDefault(); e.stopPropagation(); };

  return (
    <article className="group relative flex h-full flex-col rounded-xl border border-border bg-card p-5 shadow-sm transition-colors hover:border-primary/40"
      data-automacao={automation.id}>
      <Link href={`/automations/${automation.id}`} className="absolute inset-0 z-0 rounded-xl" aria-label={`Abrir ${automation.name}`} />
      <div className="pointer-events-none relative flex flex-1 flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {categoryName && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">{categoryName}</p>}
            <h3 className="mt-0.5 line-clamp-2 text-lg font-semibold leading-snug text-titulo group-hover:underline">{automation.name}</h3>
          </div>
          {(onEdit || onDelete) && (
            <div className="pointer-events-auto relative z-10 flex shrink-0 opacity-60 transition-opacity group-hover:opacity-100">
              {onEdit && (
                <button className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={`Editar ${automation.name}`}
                  title="Editar" onClick={(e) => { parar(e); onEdit(automation); }}>
                  <Pencil className="h-4 w-4" />
                </button>
              )}
              {onDelete && (
                <button className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-destructive" aria-label={`Arquivar ${automation.name}`}
                  title="Arquivar" onClick={(e) => { parar(e); onDelete(automation); }}>
                  <Archive className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {arquivada && <Badge tone="neutral">Arquivada</Badge>}
          {!arquivada && !automation.is_active && <Badge tone="neutral">Inativa</Badge>}
          {rodando > 0 && (
            <span className="flex items-center gap-1.5 rounded-md bg-success/15 px-2 py-0.5 text-xs font-medium text-success" data-testid="rodando">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" /> Rodando{rodando > 1 ? ` (${rodando})` : ""}
            </span>
          )}
          {naFila > 0 && <Badge tone="info">{naFila} na fila</Badge>}
        </div>

        <p className="line-clamp-2 text-sm text-muted-foreground">{automation.description || "Sem descrição."}</p>

        <div className="mt-auto flex items-center justify-between gap-3 border-t border-border pt-3">
          <p className="min-w-0 truncate text-sm text-muted-foreground" data-testid="ultima-execucao">
            {ultima && situacao ? (
              <>Última {relativo(ultima.quando)} · <span className={situacao.tom === "destructive" ? "text-destructive" : undefined}>{situacao.texto}</span></>
            ) : "Ainda não rodou"}
          </p>
          {onRestore ? (
            <Button size="sm" variant="outline" className="pointer-events-auto relative z-10" onClick={(e) => { parar(e); onRestore(automation); }}>
              Restaurar
            </Button>
          ) : onExecutar && (
            <Button size="sm" className="pointer-events-auto relative z-10" onClick={(e) => { parar(e); onExecutar(automation); }}>
              <Play className="h-4 w-4" /> Executar
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
