"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckCircle2, CircleAlert, Hand, Play } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { PageTitle } from "@/components/shared/page-title";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { haQuanto } from "@/lib/tempo";
import { cn, formatDateTime } from "@/lib/utils";

/*
 * Pendências (13/11/2026): itens que pararam esperando uma pessoa (ex.: rubricas a parametrizar).
 * Depois de resolver, alguém aperta "Continuar processo" (no e-mail ou aqui) e entra na Fila uma
 * execução só com esses itens. Vale uma vez: depois, qualquer caminho mostra quem já continuou.
 */

type Item = { id: string; item: string; rotulo: string | null; motivo: string | null; situacao: "aguardando" | "continuada" | "substituida" | string;
  desde: string; resolvida_em: string | null; resolvida_via: string | null; resolvida_por: string | null; continuacao_execucao_id: string | null };
type Resolucao = { situacao: string; resolvida_em: string | null; resolvida_via: string | null; resolvida_por: string | null;
  continuacao_execucao_id: string | null };
type Situacao = { execucao_id: string; automacao: { id: number; nome: string | null }; avisado_em: string | null; itens: Item[];
  aguardando: number; pode_continuar: boolean; resolucao: Resolucao | null };
type Grupo = { execucao_id: string; automacao: { id: number; nome: string | null }; pode_continuar: boolean; desde: string; itens: Item[] };

function textoDaResolucao(r: Resolucao): string {
  if (r.situacao === "substituida") return `O item rodou de novo em outra execução ${haQuanto(r.resolvida_em)}.`;
  const quem = r.resolvida_por ? ` por ${r.resolvida_por}` : "";
  const via = r.resolvida_via === "email" ? " pelo botão do e-mail" : r.resolvida_via === "portal" ? " pelo Portal" : "";
  return `Este processo já foi continuado ${haQuanto(r.resolvida_em)}${quem}${via}.`;
}

function JaContinuado({ resolucao }: { resolucao: Resolucao }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-muted/30 p-5" data-testid="ja-continuado">
      <CheckCircle2 className="h-6 w-6 shrink-0 text-success" />
      <div className="min-w-0 flex-1">
        <p className="text-lg font-semibold text-titulo">{textoDaResolucao(resolucao)}</p>
        <p className="text-sm text-muted-foreground">O botão "Continuar processo" vale uma vez: não há nada para continuar de novo.</p>
      </div>
      {resolucao.continuacao_execucao_id && (
        <Button variant="outline" asChild><Link href={`/execucoes/${resolucao.continuacao_execucao_id}`}>Ver a execução</Link></Button>
      )}
    </div>
  );
}

function ListaDeItens({ itens }: { itens: Item[] }) {
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-card" data-testid="itens-da-pendencia">
      {itens.map((i) => (
        <li key={i.id} className="flex items-start gap-3 px-4 py-3" data-item={i.item}>
          {i.situacao === "aguardando" ? <Hand className="mt-0.5 h-5 w-5 shrink-0 text-warning" /> : <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />}
          <div className="min-w-0 flex-1">
            <p className="font-medium">{i.rotulo ?? i.item} <span className="font-mono text-xs text-muted-foreground">{i.rotulo ? i.item : ""}</span></p>
            <p className="text-sm text-muted-foreground">{i.motivo ?? "precisa de uma pessoa"}</p>
          </div>
          <Badge tone={i.situacao === "aguardando" ? "warning" : "success"}>
            {i.situacao === "aguardando" ? "aguardando" : i.situacao === "substituida" ? "rodou de novo" : "continuado"}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

function useContinuar(aoTerminar: () => Promise<unknown>) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [ocupado, setOcupado] = useState(false);
  const [feito, setFeito] = useState<{ execucao_id: string; itens: string[] } | null>(null);

  async function continuar(caminho: string, corpo?: unknown) {
    setOcupado(true);
    try {
      const r = await apiRequest<{ execucao_id: string; itens: string[] }>(caminho, { token, method: "POST",
        body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      setFeito(r);
      toast({ title: "Processo continuado: entrou na fila", kind: "success" });
    } catch (err) {
      toast({ title: "Não foi possível continuar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setOcupado(false);
      await aoTerminar();
    }
  }
  return { continuar, ocupado, feito };
}

function Continuado({ feito }: { feito: { execucao_id: string; itens: string[] } }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-success/30 bg-success/5 p-5" data-testid="continuado">
      <CheckCircle2 className="h-6 w-6 shrink-0 text-success" />
      <p className="min-w-0 flex-1 text-lg font-semibold text-titulo">
        Processo continuado: {feito.itens.length} {feito.itens.length === 1 ? "item entrou" : "itens entraram"} na fila.
      </p>
      <Button asChild><Link href={`/execucoes/${feito.execucao_id}`}>Acompanhar</Link></Button>
    </div>
  );
}

/** Onde o botão "Continuar processo" do e-mail leva (com login). */
export function PaginaDoAviso({ avisoId }: { avisoId: string }) {
  const dados = useApi<Situacao>(`/pendencias/avisos/${avisoId}`);
  const { continuar, ocupado, feito } = useContinuar(dados.refetch);
  const s = dados.data;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageTitle eyebrow="Pendência" title={s ? `${s.automacao.nome ?? "Automação"} precisa de você` : "Pendência"}
        description={s?.avisado_em ? `Aviso enviado ${haQuanto(s.avisado_em)} (${formatDateTime(s.avisado_em)}).` : undefined} />
      {dados.error ? <ErrorState message={dados.error} onRetry={dados.refetch} /> : !s ? <div className="skeleton h-48 rounded-xl" /> : (
        <>
          {feito ? <Continuado feito={feito} /> : s.resolucao && !s.aguardando ? <JaContinuado resolucao={s.resolucao} /> : (
            <div className="flex flex-wrap items-center gap-4 rounded-xl border border-warning/40 bg-warning/5 p-5">
              <CircleAlert className="h-6 w-6 shrink-0 text-warning" />
              <p className="min-w-0 flex-1 text-base">
                Resolveu o que faltava? Continue o processo: {s.aguardando === 1 ? "o item entra" : `os ${s.aguardando} itens entram`} na fila de novo.
              </p>
              {s.pode_continuar ? (
                <Button size="lg" disabled={ocupado} onClick={() => void continuar(`/pendencias/avisos/${avisoId}/continuar`)}>
                  <Play className="h-5 w-5" /> {ocupado ? "Continuando..." : "Continuar processo"}
                </Button>
              ) : <p className="text-sm text-muted-foreground">Você não pode executar esta automação: peça a quem pode.</p>}
            </div>
          )}
          <ListaDeItens itens={s.itens} />
          <p className="text-sm text-muted-foreground">
            <Link href={`/execucoes/${s.execucao_id}`} className="text-primary hover:underline">Ver a execução que parou</Link>
          </p>
        </>
      )}
    </div>
  );
}

/** Todas as pendências aguardando, por execução. */
export function PaginaDePendencias() {
  const dados = useApi<{ execucoes: Grupo[] }>("/pendencias");
  const { continuar, ocupado, feito } = useContinuar(dados.refetch);
  const grupos = Array.isArray(dados.data?.execucoes) ? dados.data.execucoes : [];
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Monitorar" title="Pendências"
        description="Itens que pararam esperando uma pessoa. Depois de resolver, continue o processo: só esses itens entram na fila." />
      {feito && <Continuado feito={feito} />}
      {dados.error ? <ErrorState message={dados.error} onRetry={dados.refetch} /> : !dados.data ? <div className="skeleton h-48 rounded-xl" /> :
        grupos.length === 0 ? <EmptyState icon={CheckCircle2} title="Nada aguardando" description="Quando um item parar esperando uma pessoa, ele aparece aqui." /> : (
          <div className="space-y-4" data-testid="lista-de-pendencias">
            {grupos.map((g) => (
              <section key={g.execucao_id} className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-sm" data-execucao={g.execucao_id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-titulo">{g.automacao.nome ?? "Automação"}</h2>
                    <p className="text-sm text-muted-foreground">
                      {g.itens.length} {g.itens.length === 1 ? "item aguardando" : "itens aguardando"} · desde {haQuanto(g.desde)} ·{" "}
                      <Link href={`/execucoes/${g.execucao_id}`} className="text-primary hover:underline">ver execução</Link>
                    </p>
                  </div>
                  {g.pode_continuar && (
                    <Button disabled={ocupado} onClick={() => void continuar(`/pendencias/execucoes/${g.execucao_id}/continuar`, {})}>
                      <Play className="h-4 w-4" /> Continuar processo
                    </Button>
                  )}
                </div>
                <ListaDeItens itens={g.itens} />
              </section>
            ))}
          </div>
        )}
    </div>
  );
}

/** Na tela da execução: os itens aguardando e o botão. */
export function PendenciasDaExecucao({ execucaoId }: { execucaoId: string }) {
  const dados = useApi<Situacao>(`/pendencias/execucoes/${execucaoId}`);
  const { continuar, ocupado, feito } = useContinuar(dados.refetch);
  const s = dados.data;
  if (feito) return <Continuado feito={feito} />;
  if (!s || !Array.isArray(s.itens) || !s.aguardando) return null;
  return (
    <div className={cn("flex flex-wrap items-center gap-4 rounded-xl border border-warning/40 bg-warning/5 p-4")} data-testid="pendencias-da-execucao">
      <Hand className="h-5 w-5 shrink-0 text-warning" />
      <p className="min-w-0 flex-1">
        <b>{s.aguardando} {s.aguardando === 1 ? "item aguardando" : "itens aguardando"} uma pessoa</b>{" "}
        <span className="text-muted-foreground">({s.itens.filter((i) => i.situacao === "aguardando").map((i) => i.rotulo ?? i.item).join(", ")})</span>
      </p>
      {s.pode_continuar && (
        <Button size="sm" disabled={ocupado} onClick={() => void continuar(`/pendencias/execucoes/${execucaoId}/continuar`, {})}>
          <Play className="h-4 w-4" /> Continuar processo
        </Button>
      )}
    </div>
  );
}
