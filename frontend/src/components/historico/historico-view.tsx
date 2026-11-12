"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, CheckCircle2, Clock3, Search, SlidersHorizontal, Timer, XCircle } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { SITUACOES } from "@/lib/acompanhar";
import { duracao, horario, relativo } from "@/lib/fila";
import type { ExecucaoNoHistorico } from "@/lib/painel";
import { cn } from "@/lib/utils";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Automation } from "@/types/automation";

type TempoDeEtapa = {
  etapa: string;
  nome: string;
  base: "item" | "automacao";
  execucoes: number;
  tipico_s: number | null;
  por_tarefa_s: number | null;
  ultimo_s: number | null;
  quando: string | null;
  falhas: number;
};
type Resumo = { dias: number | null; total: number; concluidas: number; com_falha: number; canceladas: number; duracao_media_s: number | null };
type Pagina = { execucoes: ExecucaoNoHistorico[]; cursor: string | null };

const PERIODOS = [{ dias: 1, rotulo: "Hoje" }, { dias: 7, rotulo: "7 dias" }, { dias: 30, rotulo: "30 dias" }, { dias: 0, rotulo: "Tudo" }];
const SITUACOES_FILTRO = [
  { valor: "", rotulo: "Todas" },
  { valor: "succeeded", rotulo: "Concluídas" },
  { valor: "failed", rotulo: "Com falha" },
  { valor: "cancelled", rotulo: "Canceladas" },
];

/** O que rodou, agrupado por dia, e quanto cada etapa costuma levar (a base das previsões). */
export function HistoricoView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const aba = params.get("aba") === "tempos" ? "tempos" : "execucoes";
  function abrir(nova: "execucoes" | "tempos") {
    const p = new URLSearchParams(params.toString());
    if (nova === "tempos") p.set("aba", "tempos");
    else p.delete("aba");
    router.replace(p.size ? `${pathname}?${p}` : pathname);
  }
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Monitorar</p>
          <h1 className="titulo-condensado text-4xl">Histórico</h1>
          <p className="mt-1 max-w-3xl text-base text-muted-foreground">
            {aba === "execucoes"
              ? "O que já rodou: quando, quanto tempo levou comparado ao previsto e como terminou."
              : "Quanto cada etapa costuma levar para um item. O Portal usa esses tempos para prever quando cada execução termina, na Fila e no Painel."}
          </p>
        </div>
        <div className="flex rounded-lg border border-border bg-card p-1" role="tablist" aria-label="Seções do histórico">
          {([["execucoes", "Execuções"], ["tempos", "Quanto tempo leva"]] as const).map(([chave, rotulo]) => (
            <button key={chave} role="tab" aria-selected={aba === chave} onClick={() => abrir(chave)}
              className={cn("rounded-md px-4 py-1.5 text-sm font-medium",
                aba === chave ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
              {rotulo}
            </button>
          ))}
        </div>
      </div>
      {aba === "execucoes" ? <Execucoes /> : <Tempos />}
    </div>
  );
}

function rotuloDoDia(iso: string): string {
  const d = new Date(iso);
  const dia = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dif = Math.round((dia(new Date()) - dia(d)) / 86_400_000);
  if (dif === 0) return "Hoje";
  if (dif === 1) return "Ontem";
  const texto = d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function Execucoes() {
  const { token } = useAuth();
  const [dias, setDias] = useState(7);
  const [situacao, setSituacao] = useState("");
  const [automacao, setAutomacao] = useState("");
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);
  const ativos = [situacao, automacao, buscaAplicada].filter(Boolean).length;
  const automacoes = useApi<Automation[]>("/automations");
  const [mais, setMais] = useState<ExecucaoNoHistorico[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 350);
    return () => clearTimeout(t);
  }, [busca]);

  const params = new URLSearchParams({ limite: "40" });
  if (buscaAplicada) params.set("busca", buscaAplicada);
  if (situacao) params.set("situacao", situacao);
  if (automacao) params.set("automacao", automacao);
  if (dias) params.set("dias", String(dias));
  const pagina = useApi<Pagina>(`/historico?${params}`, { pollMs: 60000 });
  const resumo = useApi<Resumo>(`/historico/resumo?${dias ? `dias=${dias}` : "dias=3650"}${automacao ? `&automacao=${automacao}` : ""}`, { pollMs: 60000 });

  useEffect(() => {
    setMais([]);
    setCursor(pagina.data?.cursor ?? null);
  }, [pagina.data]);

  async function carregarMais() {
    if (!cursor) return;
    const seguinte = new URLSearchParams(params);
    seguinte.set("antes", cursor);
    const resposta = await apiRequest<Pagina>(`/historico?${seguinte}`, { token });
    setMais((m) => [...m, ...resposta.execucoes]);
    setCursor(resposta.cursor);
  }

  const linhas = [...(pagina.data?.execucoes ?? []), ...mais];
  const porDia = useMemo(() => {
    const grupos: Array<{ dia: string; rotulo: string; itens: ExecucaoNoHistorico[] }> = [];
    for (const h of linhas) {
      const quando = h.concluida_em ?? h.iniciada_em ?? "";
      const chave = quando ? new Date(quando).toDateString() : "sem data";
      const atual = grupos.at(-1);
      if (atual && atual.dia === chave) atual.itens.push(h);
      else grupos.push({ dia: chave, rotulo: quando ? rotuloDoDia(quando) : "Sem data", itens: [h] });
    }
    return grupos;
  }, [linhas]);

  const r = resumo.data;
  const chip = (ativo: boolean) => cn("rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors",
    ativo ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground");
  return (
    <section className="space-y-6">
      <dl className="faixa-noite grid grid-cols-2 gap-px overflow-hidden rounded-xl md:grid-cols-4" data-testid="resumo-historico">
        {[
          { rotulo: "Execuções", valor: r?.total, icone: Clock3 },
          { rotulo: "Concluídas", valor: r?.concluidas, icone: CheckCircle2 },
          { rotulo: "Com falha", valor: r?.com_falha, icone: XCircle, alerta: (r?.com_falha ?? 0) > 0 },
          { rotulo: "Tempo médio", valor: r?.duracao_media_s != null ? duracao(r.duracao_media_s) : "—", icone: Timer },
        ].map(({ rotulo, valor, icone: Icone, alerta }) => (
          <div key={rotulo} className="px-6 py-4">
            <dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] faixa-rotulo"><Icone className="h-4 w-4" /> {rotulo}</dt>
            <dd className={cn("titulo-condensado mt-1 text-3xl leading-none", alerta ? "faixa-alerta" : "faixa-valor")}>{valor ?? "…"}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border border-border bg-card p-1" role="group" aria-label="Período">
          {PERIODOS.map((p) => <button key={p.rotulo} onClick={() => setDias(p.dias)} aria-pressed={dias === p.dias} className={chip(dias === p.dias)}>{p.rotulo}</button>)}
        </div>
        <Button variant={filtrosAbertos || ativos ? "secondary" : "outline"} onClick={() => setFiltrosAbertos((v) => !v)} aria-expanded={filtrosAbertos}>
          <SlidersHorizontal className="h-4 w-4" /> Filtros{ativos ? ` (${ativos})` : ""}
        </Button>
        {ativos > 0 && (
          <button onClick={() => { setSituacao(""); setAutomacao(""); setBusca(""); }} className="text-sm font-medium text-primary hover:underline">Limpar filtros</button>
        )}
      </div>
      {filtrosAbertos && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4">
          <div className="flex rounded-lg border border-border bg-background p-1" role="group" aria-label="Situação">
            {SITUACOES_FILTRO.map((s) => <button key={s.rotulo} onClick={() => setSituacao(s.valor)} aria-pressed={situacao === s.valor} className={chip(situacao === s.valor)}>{s.rotulo}</button>)}
          </div>
          <select value={automacao} onChange={(e) => setAutomacao(e.target.value)} aria-label="Automação"
            className="h-11 min-w-[14rem] rounded-lg border border-input bg-background px-3 text-sm">
            <option value="">Todas as automações</option>
            {(Array.isArray(automacoes.data) ? automacoes.data : []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <label className="relative min-w-[16rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar automação ou item (ex.: 5081)"
              className="h-11 w-full rounded-lg border border-input bg-background pl-11 pr-3 text-base" aria-label="Buscar" />
          </label>
        </div>
      )}

      {pagina.error && !pagina.data ? (
        <ErrorState message={pagina.error} onRetry={() => void pagina.refetch()} />
      ) : !pagina.data ? (
        <div className="skeleton h-64 w-full rounded-xl" />
      ) : linhas.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-muted-foreground">Nenhuma execução terminada com esses filtros.</p>
      ) : (
        <div className="space-y-6" data-testid="historico">
          {porDia.map((g) => (
            <section key={g.dia} className="space-y-2">
              <h2 className="flex items-baseline gap-3 text-lg font-semibold text-titulo">
                {g.rotulo} <span className="text-sm font-normal text-muted-foreground">{g.itens.length} execução(ões)</span>
              </h2>
              <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                <div className="hidden grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_minmax(0,1.2fr)_9rem] gap-4 border-b border-border bg-muted/50 px-5 py-2.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground md:grid">
                  <span>Automação e itens</span><span>Horário</span><span>Duração</span><span className="text-right">Situação</span>
                </div>
                <ol className="divide-y divide-border">
                  {g.itens.map((h) => <LinhaDoHistorico key={h.execucao_id} h={h} />)}
                </ol>
              </div>
            </section>
          ))}
        </div>
      )}
      {cursor && linhas.length > 0 && (
        <div className="text-center">
          <Button variant="outline" onClick={() => void carregarMais()}>Carregar mais</Button>
        </div>
      )}
    </section>
  );
}

/** "8 min acima do previsto" quando passou mais que 1 min e 10%; senão "dentro do previsto". */
function comparacao(h: ExecucaoNoHistorico): { texto: string; tom: string } {
  if (h.duracao_s == null) return { texto: "sem duração", tom: "text-muted-foreground" };
  if (h.previsto_s == null) return { texto: "sem previsão no início", tom: "text-muted-foreground" };
  const dif = h.duracao_s - h.previsto_s;
  if (dif > Math.max(60, h.previsto_s * 0.1)) return { texto: `${duracao(dif).replace("~ ", "")} acima do previsto (${duracao(h.previsto_s)})`, tom: "text-warning" };
  if (-dif > Math.max(60, h.previsto_s * 0.1)) return { texto: `${duracao(-dif).replace("~ ", "")} abaixo do previsto`, tom: "text-success" };
  return { texto: `dentro do previsto (${duracao(h.previsto_s)})`, tom: "text-muted-foreground" };
}

export function LinhaDoHistorico({ h }: { h: ExecucaoNoHistorico }) {
  const s = SITUACOES[h.status] ?? { texto: h.status, tom: "neutral" as const };
  const c = comparacao(h);
  const itens = h.total_itens ? `${h.itens.join(", ")}${h.total_itens > h.itens.length ? ` e mais ${h.total_itens - h.itens.length}` : ""}` : "sem itens";
  return (
    <li>
      <Link href={`/execucoes/${h.execucao_id}`} data-execucao={h.execucao_id}
        className="grid gap-x-4 gap-y-1.5 px-5 py-4 transition-colors hover:bg-muted md:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_minmax(0,1.2fr)_9rem] md:items-center">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-titulo">{h.automacao ?? "Automação"}</p>
          <p className="truncate text-sm text-muted-foreground">{itens}{h.maquinas ? ` · ${h.maquinas}` : ""}</p>
          {h.falha && <p className="mt-1 truncate text-sm text-destructive" title={h.falha}>{h.falha}</p>}
        </div>
        <p className="flex items-center gap-1.5 text-sm tabular-nums text-muted-foreground">
          {h.iniciada_em ? horario(h.iniciada_em) : "—"} <ArrowRight className="h-3.5 w-3.5" /> {h.concluida_em ? horario(h.concluida_em) : "—"}
        </p>
        <div>
          <p className="text-xl font-semibold leading-tight text-titulo">{h.duracao_s != null ? duracao(h.duracao_s) : "—"}</p>
          <p className={cn("text-sm", c.tom)}>{c.texto}</p>
        </div>
        <Badge tone={s.tom} className="justify-self-start px-3 py-1 text-sm md:justify-self-end">{s.texto}</Badge>
      </Link>
    </li>
  );
}

type ItemDaLista = { chave: string; rotulo: string };

function Tempos() {
  const automacoes = useApi<Automation[]>("/automations");
  const [automacao, setAutomacao] = useState("");
  const itens = useApi<{ itens: ItemDaLista[] }>(automacao ? `/automations/${automacao}/itens?limite=500` : null);
  const [item, setItem] = useState("");
  const [filtro, setFiltro] = useState("");
  const tempos = useApi<{ etapas: TempoDeEtapa[] }>(automacao && item ? `/automations/${automacao}/tempos?item=${encodeURIComponent(item)}` : null);
  useEffect(() => { setItem(""); setFiltro(""); }, [automacao]);

  const lista = (itens.data?.itens ?? []).filter((i) => {
    const t = filtro.trim().toLowerCase();
    return !t || i.chave.toLowerCase().includes(t) || i.rotulo.toLowerCase().includes(t);
  });
  const etapas = tempos.data?.etapas ?? [];
  const maior = Math.max(1, ...etapas.map((e) => Math.max(e.tipico_s ?? 0, e.ultimo_s ?? 0)));
  const total = etapas.reduce((s, e) => s + (e.tipico_s ?? 0), 0);
  const nomeDoItem = itens.data?.itens.find((i) => i.chave === item)?.rotulo;

  return (
    <section className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]" data-testid="tempos">
      <div className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">1. Automação</p>
        <select value={automacao} onChange={(e) => setAutomacao(e.target.value)} aria-label="Automação"
          className="h-11 w-full rounded-lg border border-input bg-card px-3">
          <option value="">Escolha a automação…</option>
          {(Array.isArray(automacoes.data) ? automacoes.data : []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        {automacao && (
          <>
            <p className="pt-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">2. Item</p>
            {itens.error ? (
              <input value={item} onChange={(e) => setItem(e.target.value.trim())} placeholder="Código do item, ex.: 5081"
                className="h-11 w-full rounded-lg border border-input bg-card px-3" aria-label="Código do item" />
            ) : (
              <>
                <input value={filtro} onChange={(e) => setFiltro(e.target.value)} placeholder="Filtrar por código ou nome"
                  className="h-10 w-full rounded-lg border border-input bg-card px-3 text-sm" aria-label="Filtrar itens" />
                <ul className="max-h-[26rem] divide-y divide-border overflow-y-auto rounded-lg border border-border bg-card" role="listbox" aria-label="Itens">
                  {!itens.data ? <li className="p-3"><div className="skeleton h-24 rounded" /></li> : lista.length === 0 ? (
                    <li className="p-4 text-sm text-muted-foreground">Nenhum item.</li>
                  ) : lista.map((i) => (
                    <li key={i.chave} role="option" aria-selected={item === i.chave}>
                      <button onClick={() => setItem(i.chave)} className={cn("flex w-full items-baseline gap-3 px-3 py-2 text-left text-sm hover:bg-muted",
                        item === i.chave && "bg-primary/10 font-semibold text-titulo")}>
                        <span className="w-14 shrink-0 tabular-nums text-muted-foreground">{i.chave}</span>
                        <span className="truncate">{i.rotulo}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </div>

      <div>
        {!automacao || !item ? (
          <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center text-muted-foreground">
            Escolha a automação e um item para ver quanto cada etapa costuma levar.
          </div>
        ) : tempos.error ? (
          <ErrorState message={tempos.error} />
        ) : !tempos.data ? (
          <div className="skeleton h-64 w-full rounded-xl" />
        ) : (
          <div className="space-y-4 rounded-xl border border-border bg-card p-6 shadow-sm" data-testid="tempos-do-item">
            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
              <div>
                <p className="text-sm text-muted-foreground">Item {item}</p>
                <p className="text-2xl font-semibold text-titulo">{nomeDoItem ?? item}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Costuma levar, somando as etapas</p>
                <p className="text-3xl font-semibold text-titulo">{total ? duracao(total) : "sem histórico"}</p>
              </div>
            </div>
            <ul className="space-y-4">
              {etapas.map((t) => (
                <li key={t.etapa} className="grid gap-2 md:grid-cols-[17rem_minmax(0,1fr)_14rem] md:items-center">
                  <div>
                    <p className="font-medium text-titulo">{t.nome}</p>
                    <p className="text-xs text-muted-foreground">
                      {t.base === "automacao" ? "uma vez por execução" : "para este item"} · {t.execucoes} vez(es)
                      {t.falhas ? <span className="text-warning"> · {t.falhas} com falha</span> : null}
                    </p>
                  </div>
                  <div className="space-y-1" aria-hidden>
                    <div className="h-3 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${((t.tipico_s ?? 0) / maior) * 100}%` }} />
                    </div>
                    {t.ultimo_s != null && (
                      <div className="h-1.5 overflow-hidden rounded-full bg-transparent">
                        <div className={cn("h-full rounded-full", t.tipico_s != null && t.ultimo_s > t.tipico_s * 1.1 ? "bg-warning" : "bg-muted-foreground/50")}
                          style={{ width: `${(t.ultimo_s / maior) * 100}%` }} />
                      </div>
                    )}
                  </div>
                  <div className="md:text-right">
                    <p className="text-lg font-semibold text-titulo">{t.tipico_s != null ? duracao(t.tipico_s) : <span className="text-base font-normal text-warning">sem histórico</span>}</p>
                    {t.ultimo_s != null && (
                      <p className="text-xs text-muted-foreground">última: {duracao(t.ultimo_s)}{t.quando ? ` · ${relativo(t.quando)}` : ""}</p>
                    )}
                    {t.por_tarefa_s != null && <p className="text-xs text-muted-foreground">{duracao(t.por_tarefa_s)} por tarefa</p>}
                  </div>
                </li>
              ))}
            </ul>
            <p className="border-t border-border pt-3 text-xs text-muted-foreground">
              Barra grossa: o tempo típico. Barra fina: a última vez (amarela quando passou mais de 10% do típico).
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
