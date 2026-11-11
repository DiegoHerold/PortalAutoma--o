"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, SlidersHorizontal, X } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { SITUACOES } from "@/lib/acompanhar";
import { duracao, horario } from "@/lib/fila";
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

export function HistoricoView() {
  const [aba, setAba] = useState<"execucoes" | "tempos">("execucoes");
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Monitorar</p>
          <h1 className="titulo-condensado text-4xl">Histórico</h1>
        </div>
        <div className="flex rounded-lg border border-border bg-card p-1" role="tablist">
          {([["execucoes", "Execuções"], ["tempos", "Tempos por item"]] as const).map(([chave, rotulo]) => (
            <button key={chave} role="tab" aria-selected={aba === chave} onClick={() => setAba(chave)}
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

function Execucoes() {
  const { token } = useAuth();
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [filtros, setFiltros] = useState(false);
  const [situacao, setSituacao] = useState("");
  const [automacao, setAutomacao] = useState("");
  const automacoes = useApi<Automation[]>(filtros ? "/automations" : null);
  const [mais, setMais] = useState<ExecucaoNoHistorico[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 350);
    return () => clearTimeout(t);
  }, [busca]);

  const params = new URLSearchParams({ limite: "30" });
  if (buscaAplicada) params.set("busca", buscaAplicada);
  if (situacao) params.set("situacao", situacao);
  if (automacao) params.set("automacao", automacao);
  const pagina = useApi<{ execucoes: ExecucaoNoHistorico[]; cursor: string | null }>(`/historico?${params}`, { pollMs: 60000 });

  useEffect(() => {
    setMais([]);
    setCursor(pagina.data?.cursor ?? null);
  }, [pagina.data]);

  async function carregarMais() {
    if (!cursor) return;
    const seguinte = new URLSearchParams(params);
    seguinte.set("antes", cursor);
    const resposta = await apiRequest<{ execucoes: ExecucaoNoHistorico[]; cursor: string | null }>(`/historico?${seguinte}`, { token });
    setMais((m) => [...m, ...resposta.execucoes]);
    setCursor(resposta.cursor);
  }

  const linhas = [...(pagina.data?.execucoes ?? []), ...mais];
  const filtrosAtivos = [situacao, automacao].filter(Boolean).length;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <label className="relative min-w-[16rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por automação ou item"
            className="h-12 w-full rounded-lg border border-input bg-card pl-11 pr-3 text-base" aria-label="Buscar" />
        </label>
        <Button variant="outline" className="h-12" onClick={() => setFiltros((v) => !v)} aria-expanded={filtros}>
          <SlidersHorizontal className="h-4 w-4" /> Filtros{filtrosAtivos ? ` (${filtrosAtivos})` : ""}
        </Button>
      </div>
      {filtros && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4">
          <select value={situacao} onChange={(e) => setSituacao(e.target.value)} className="h-11 rounded-md border border-input bg-background px-3" aria-label="Situação">
            <option value="">Todas as situações</option>
            {["succeeded", "partially_succeeded", "failed", "cancelled", "timed_out", "lost"].map((s) => (
              <option key={s} value={s}>{SITUACOES[s]?.texto ?? s}</option>
            ))}
          </select>
          <select value={automacao} onChange={(e) => setAutomacao(e.target.value)} className="h-11 rounded-md border border-input bg-background px-3" aria-label="Automação">
            <option value="">Todas as automações</option>
            {(automacoes.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          {filtrosAtivos > 0 && (
            <Button variant="ghost" onClick={() => { setSituacao(""); setAutomacao(""); }}>
              <X className="h-4 w-4" /> Limpar
            </Button>
          )}
        </div>
      )}

      {pagina.error && !pagina.data ? (
        <ErrorState message={pagina.error} onRetry={() => void pagina.refetch()} />
      ) : !pagina.data ? (
        <div className="skeleton h-64 w-full rounded-xl" />
      ) : linhas.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-muted-foreground">Nenhuma execução terminada com esses filtros.</p>
      ) : (
        <ol className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="historico">
          {linhas.map((h) => <LinhaDoHistorico key={h.execucao_id} h={h} />)}
        </ol>
      )}
      {cursor && linhas.length > 0 && (
        <div className="text-center">
          <Button variant="outline" onClick={() => void carregarMais()}>Carregar mais</Button>
        </div>
      )}
    </section>
  );
}

export function LinhaDoHistorico({ h }: { h: ExecucaoNoHistorico }) {
  const s = SITUACOES[h.status] ?? { texto: h.status, tom: "neutral" as const };
  const passou = h.duracao_s != null && h.previsto_s != null ? h.duracao_s - h.previsto_s : null;
  return (
    <li>
      <Link href={`/execucoes/${h.execucao_id}`} className="grid gap-3 px-5 py-4 hover:bg-muted md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.2fr)_auto] md:items-center">
        <div className="min-w-0">
          <p className="truncate text-lg font-semibold text-titulo">{h.automacao ?? "Automação"}</p>
          <p className="truncate text-sm text-muted-foreground">
            {h.total_itens ? `${h.itens.join(", ")}${h.total_itens > h.itens.length ? ` e mais ${h.total_itens - h.itens.length}` : ""}` : "sem itens"}
            {h.maquinas ? ` · ${h.maquinas}` : ""}
          </p>
        </div>
        <p className="text-sm text-muted-foreground">{h.concluida_em ? `${new Date(h.concluida_em).toLocaleDateString("pt-BR")} às ${horario(h.concluida_em)}` : "—"}</p>
        <div>
          <p className="titulo-condensado text-2xl leading-none">{h.duracao_s != null ? duracao(h.duracao_s) : "—"}</p>
          <p className={cn("mt-1 text-sm", passou != null && h.previsto_s != null && passou > Math.max(60, h.previsto_s * 0.1) ? "text-warning" : "text-muted-foreground")}>
            {h.previsto_s == null ? "sem previsão no início" : `previsto ${duracao(h.previsto_s)}`}
          </p>
        </div>
        <Badge tone={s.tom} className="justify-self-start px-3 py-1 text-sm md:justify-self-end">{s.texto}</Badge>
      </Link>
    </li>
  );
}

function Tempos() {
  const automacoes = useApi<Automation[]>("/automations");
  const [automacao, setAutomacao] = useState("");
  const [item, setItem] = useState("");
  const [consulta, setConsulta] = useState<string | null>(null);
  const tempos = useApi<{ etapas: TempoDeEtapa[] }>(consulta);

  return (
    <section className="space-y-4">
      <form className="flex flex-wrap gap-3" onSubmit={(e) => {
        e.preventDefault();
        if (automacao && item.trim()) setConsulta(`/automations/${automacao}/tempos?item=${encodeURIComponent(item.trim())}`);
      }}>
        <select value={automacao} onChange={(e) => setAutomacao(e.target.value)} className="h-12 min-w-[14rem] rounded-lg border border-input bg-card px-3" aria-label="Automação">
          <option value="">Escolha a automação…</option>
          {(automacoes.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <input value={item} onChange={(e) => setItem(e.target.value)} placeholder="Item, como 5066"
          className="h-12 w-48 rounded-lg border border-input bg-card px-3" aria-label="Item" />
        <Button className="h-12" type="submit" disabled={!automacao || !item.trim()}>Ver tempos</Button>
      </form>
      {!consulta ? (
        <p className="text-muted-foreground">Escolha uma automação e um item para ver quanto cada etapa costuma levar.</p>
      ) : tempos.error ? (
        <ErrorState message={tempos.error} />
      ) : !tempos.data ? (
        <div className="skeleton h-48 w-full rounded-xl" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
          <table className="w-full">
            <thead className="bg-muted text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-5 py-3">Etapa</th><th className="px-5 py-3">Típico</th><th className="px-5 py-3">Por tarefa</th>
                <th className="px-5 py-3">Última vez</th><th className="px-5 py-3">Execuções</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {tempos.data.etapas.map((t) => (
                <tr key={t.etapa}>
                  <td className="px-5 py-3 font-medium text-titulo">
                    {t.nome}
                    {t.base === "automacao" && <span className="block text-xs font-normal text-muted-foreground">da automação inteira</span>}
                  </td>
                  <td className="titulo-condensado px-5 py-3 text-xl">{t.tipico_s != null ? duracao(t.tipico_s) : <span className="font-sans text-base text-warning">sem histórico</span>}</td>
                  <td className="px-5 py-3">{t.por_tarefa_s != null ? duracao(t.por_tarefa_s) : "—"}</td>
                  <td className="px-5 py-3">{t.ultimo_s != null ? `${duracao(t.ultimo_s)} · ${t.quando ? new Date(t.quando).toLocaleDateString("pt-BR") : ""}` : "—"}</td>
                  <td className="px-5 py-3">{t.execucoes}{t.falhas ? <span className="text-warning"> · {t.falhas} com falha</span> : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
