"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileDown, History, LayoutDashboard, ListChecks, Play, Radio, SlidersHorizontal, Wrench } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { useAvisos, useSegundosDesde } from "@/hooks/use-avisos";
import type { Formulario } from "@/lib/campos";
import { duracao, horario, type VisaoFila } from "@/lib/fila";
import type { ExecucaoNoHistorico, Painel } from "@/lib/painel";
import { cn } from "@/lib/utils";
import { TecnicoDaAutomacao } from "@/components/automacao/tecnico-da-automacao";
import { ArquivosDaAutomacao } from "@/components/automacao/arquivos-da-automacao";
import { ExecutarAutomacao } from "@/components/automacao/executar-automacao";
import { EditorDeCampos } from "@/components/campos/editor-de-campos";
import { LinhaDoHistorico } from "@/components/historico/historico-view";
import { ItensDaAutomacao } from "@/components/itens/itens-da-automacao";
import { Monitor } from "@/components/painel/painel-ao-vivo";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import type { Automation } from "@/types/automation";

const ABAS = [
  { id: "geral", rotulo: "Visão geral", icone: LayoutDashboard },
  { id: "itens", rotulo: "Itens", icone: ListChecks },
  { id: "campos", rotulo: "Entradas", icone: SlidersHorizontal },
  { id: "arquivos", rotulo: "Arquivos", icone: FileDown },
  { id: "historico", rotulo: "Histórico", icone: History },
  { id: "tecnico", rotulo: "Técnico", icone: Wrench },
] as const;
type Aba = (typeof ABAS)[number]["id"];

type Historico = { cursor: string | null; execucoes: ExecucaoNoHistorico[] };

/** A automação no Catálogo: o que roda agora, a fila, o histórico, os itens, as entradas, os arquivos e o botão Executar. */
export function AutomacaoView({ id }: { id: string }) {
  const automacao = useApi<Automation>(`/automations/${id}`);
  const painel = useApi<Painel>("/painel", { pollMs: 30000 });
  const fila = useApi<VisaoFila>("/fila", { pollMs: 30000 });
  const aoVivo = useAvisos("/painel/avisos", () => { void painel.refetch(); void fila.refetch(); }, 800);
  const [aba, setAba] = useState<Aba>("geral");
  const [executando, setExecutando] = useState(false);
  const { token } = useAuth();

  useEffect(() => {
    const ler = () => {
      const hash = window.location.hash.replace("#", "");
      if (ABAS.some((a) => a.id === hash)) setAba(hash as Aba);
    };
    ler();
    window.addEventListener("hashchange", ler);
    return () => window.removeEventListener("hashchange", ler);
  }, []);

  function abrir(nova: Aba) {
    setAba(nova);
    window.history.replaceState(null, "", `#${nova}`);
  }

  if (automacao.error && !automacao.data) return <ErrorState message={automacao.error} onRetry={() => void automacao.refetch()} />;
  const numero = Number(id);
  const rodando = (painel.data?.execucoes ?? []).filter((e) => e.automation_id === numero);
  const naFila = (fila.data?.jobs ?? []).filter((j) => j.automation_id === numero);
  const nome = automacao.data?.name ?? "Automação";
  const arquivada = automacao.data?.status === "archived";

  async function restaurar() {
    await apiRequest(`/automations/${id}/restaurar`, { method: "POST", token });
    await automacao.refetch();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow"><Link href="/automations" className="hover:underline">Catálogo</Link></p>
          <h1 className="titulo-condensado text-4xl">{automacao.data ? nome : <span className="skeleton inline-block h-9 w-72 rounded" />}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-3 text-muted-foreground">
            {rodando.length > 0 ? (
              <span className="flex items-center gap-1.5 font-medium text-success"><span className="h-2 w-2 animate-pulse rounded-full bg-success" /> Rodando agora{rodando.length > 1 ? ` (${rodando.length})` : ""}</span>
            ) : <span>Parada</span>}
            {naFila.length > 0 && <span>{naFila.length} na fila</span>}
            {automacao.data?.description && <span className="truncate">{automacao.data.description}</span>}
          </p>
        </div>
        <Button size="lg" onClick={() => setExecutando(true)} disabled={!automacao.data || arquivada}>
          <Play className="h-5 w-5" /> Executar
        </Button>
      </div>

      {arquivada && (
        <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/10 px-5 py-4">
          <p><span className="font-semibold">Arquivada.</span> Fora do Catálogo e sem executar. O histórico, os itens e os campos continuam guardados.</p>
          <Button variant="outline" onClick={() => void restaurar()}>Restaurar</Button>
        </div>
      )}

      <nav aria-label="Seções da automação" className="flex gap-1 overflow-x-auto border-b border-border">
        {ABAS.map(({ id: aid, rotulo, icone: Icone }) => (
          <button key={aid} onClick={() => abrir(aid)} aria-current={aba === aid ? "page" : undefined}
            className={cn("-mb-px flex shrink-0 items-center gap-2 border-b-2 px-4 py-2.5 font-medium transition-colors",
              aba === aid ? "border-primary text-titulo" : "border-transparent text-muted-foreground hover:text-foreground")}>
            <Icone className="h-4 w-4" /> {rotulo}
          </button>
        ))}
      </nav>

      {aba === "geral" && <VisaoGeral id={id} rodando={rodando} naFila={naFila} painel={painel.data} aoVivo={aoVivo}
        verHistorico={() => abrir("historico")} verEntradas={() => abrir("campos")} />}
      {aba === "itens" && <ItensDaAutomacao id={id} embutido nome={nome} />}
      {aba === "campos" && <EditorDeCampos id={id} />}
      {aba === "arquivos" && <ArquivosDaAutomacao id={id} />}
      {aba === "historico" && <HistoricoDaAutomacao id={id} />}
      {aba === "tecnico" && <TecnicoDaAutomacao id={id} />}

      <ExecutarAutomacao id={id} nome={nome} aberto={executando} fechar={() => setExecutando(false)}
        pedido={() => { void fila.refetch(); abrir("geral"); }} />
    </div>
  );
}

function VisaoGeral({ id, rodando, naFila, painel, aoVivo, verHistorico, verEntradas }: {
  id: string;
  rodando: Painel["execucoes"];
  naFila: VisaoFila["jobs"];
  painel: Painel | null;
  aoVivo: boolean;
  verHistorico: () => void;
  verEntradas: () => void;
}) {
  const passou = useSegundosDesde(painel?.gerado_em, rodando.length > 0);
  const ultimas = useApi<Historico>(`/historico?automacao=${id}&limite=5`);
  const form = useApi<Formulario>(`/automations/${id}/formulario`);
  const pede = (form.data?.entrada ?? []).filter((c) => !c.fora_de_uso);
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="titulo-condensado text-2xl">Agora</h2>
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground"><Radio className={cn("h-4 w-4", aoVivo && "text-success")} /> {aoVivo ? "Ao vivo" : "Relendo a cada 30 s"}</span>
        </div>
        {!painel ? <div className="skeleton h-48 rounded-xl" /> : rodando.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border px-6 py-8 text-muted-foreground">
            Nada rodando desta automação agora.
          </p>
        ) : (
          <div className="grid gap-5 xl:grid-cols-2" data-testid="rodando-agora">
            {rodando.map((e) => <Monitor key={e.execucao_id} e={e} passou={passou} />)}
          </div>
        )}
      </section>

      {form.data && (
        <section className="space-y-2" data-testid="o-que-pede">
          <div className="flex items-center justify-between">
            <h2 className="titulo-condensado text-2xl">Para executar</h2>
            <button onClick={verEntradas} className="text-sm font-medium text-primary hover:underline">Ver as entradas</button>
          </div>
          <p className="flex flex-wrap items-center gap-2 text-muted-foreground">
            {form.data.item && <span className="rounded-md border border-border bg-card px-2.5 py-1 font-medium text-foreground">{form.data.item.nome}s</span>}
            {pede.map((c) => (
              <span key={c.chave} className="rounded-md bg-secondary px-2.5 py-1 text-secondary-foreground">{c.rotulo}{c.obrigatorio ? " *" : ""}</span>
            ))}
            {!form.data.item && pede.length === 0 && <span>Não pede nenhuma informação.</span>}
          </p>
        </section>
      )}

      {naFila.length > 0 && (
        <section className="space-y-3">
          <h2 className="titulo-condensado text-2xl">Na fila</h2>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="na-fila">
            {naFila.map((j) => (
              <li key={j.job_id} className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3">
                <span className="titulo-condensado w-8 text-xl text-muted-foreground">{j.posicao}</span>
                <span className="min-w-0 flex-1 truncate">{j.itens.length ? j.itens.join(", ") : "sem itens"}</span>
                <span className="text-sm text-muted-foreground">{j.inicio_previsto ? `começa ${horario(j.inicio_previsto)}` : "sem previsão"}</span>
                <span className="text-sm text-muted-foreground">{j.estimativa_s != null ? duracao(j.estimativa_s) : ""}</span>
              </li>
            ))}
          </ul>
          <Link href="/fila" className="text-sm font-medium text-primary hover:underline">Ver a fila inteira</Link>
        </section>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="titulo-condensado text-2xl">Últimas execuções</h2>
          <button onClick={verHistorico} className="text-sm font-medium text-primary hover:underline">Ver o histórico</button>
        </div>
        {!ultimas.data ? <div className="skeleton h-32 rounded-xl" /> : ultimas.data.execucoes.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border px-6 py-8 text-center text-muted-foreground">Esta automação ainda não rodou.</p>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            {ultimas.data.execucoes.map((h) => <LinhaDoHistorico key={h.execucao_id} h={h} />)}
          </ul>
        )}
      </section>
    </div>
  );
}

function HistoricoDaAutomacao({ id }: { id: string }) {
  const [antes, setAntes] = useState<string | null>(null);
  const [linhas, setLinhas] = useState<ExecucaoNoHistorico[]>([]);
  const pagina = useApi<Historico>(`/historico?automacao=${id}&limite=30${antes ? `&antes=${encodeURIComponent(antes)}` : ""}`);
  useEffect(() => {
    if (pagina.data) setLinhas((atuais) => (antes ? [...atuais, ...pagina.data!.execucoes] : pagina.data!.execucoes));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagina.data]);
  return (
    <section className="space-y-3">
      <h2 className="titulo-condensado text-2xl">Histórico</h2>
      {!pagina.data && linhas.length === 0 ? <div className="skeleton h-64 rounded-xl" /> : linhas.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-6 py-8 text-center text-muted-foreground">Esta automação ainda não rodou.</p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="historico-da-automacao">
          {linhas.map((h) => <LinhaDoHistorico key={h.execucao_id} h={h} />)}
        </ul>
      )}
      {pagina.data?.cursor && <Button variant="outline" onClick={() => setAntes(pagina.data!.cursor)}>Carregar mais</Button>}
    </section>
  );
}
