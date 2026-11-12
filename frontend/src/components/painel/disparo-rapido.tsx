"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { History, Play, RotateCcw, Search } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { SITUACOES } from "@/lib/acompanhar";
import { relativo } from "@/lib/fila";
import { cn } from "@/lib/utils";
import { ExecutarAutomacao } from "@/components/automacao/executar-automacao";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BotaoContinuar } from "@/components/painel/controle-da-execucao";
import { Modal } from "@/components/ui/modal";

type Executavel = { id: number; nome: string; descricao: string | null };
type Recente = {
  automation_id: number;
  automacao: string;
  pode_executar: boolean;
  pode_controlar?: boolean;
  ultima: { execucao_id: string; status: string; quando: string | null; maquinas: string[]; itens: string[];
            continuada_em?: string | null };
};
type Recentes = { automacoes: Recente[]; maquinas: Array<{ id: string; nome: string }> };
type Disparo = { id: number; nome: string; itens?: string[] };


/** Abre a janela Executar de qualquer automação; quem chama decide o que mostrar para disparar. */
export function useDisparo(pedido?: () => void) {
  const [disparo, setDisparo] = useState<Disparo | null>(null);
  const janela = disparo ? (
    <ExecutarAutomacao key={`${disparo.id}-${(disparo.itens ?? []).join(",")}`} id={String(disparo.id)} nome={disparo.nome}
      aberto fechar={() => setDisparo(null)} preEscolhidos={disparo.itens ?? []} pedido={pedido} />
  ) : null;
  return { disparar: setDisparo, janela };
}

/** Botão do topo do Painel: acha uma automação pelo nome e já abre a janela Executar. */
export function BotaoExecutar({ disparar }: { disparar: (d: Disparo) => void }) {
  const [aberta, setAberta] = useState(false);

  useEffect(() => {
    // Atalho: "e" fora de um campo de texto abre a busca.
    function tecla(ev: KeyboardEvent) {
      const alvo = ev.target as HTMLElement | null;
      if (ev.key.toLowerCase() !== "e" || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      if (alvo && (alvo.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName))) return;
      ev.preventDefault();
      setAberta(true);
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  return (
    <>
      <Button size="lg" onClick={() => setAberta(true)} title="Executar uma automação (atalho: E)">
        <Play className="h-5 w-5" /> Executar automação
      </Button>
      {aberta && <BuscaParaExecutar fechar={() => setAberta(false)} escolher={(a) => { setAberta(false); disparar(a); }} />}
    </>
  );
}

function BuscaParaExecutar({ fechar, escolher }: { fechar: () => void; escolher: (d: Disparo) => void }) {
  const lista = useApi<{ automacoes: Executavel[] }>("/painel/executaveis");
  const [busca, setBusca] = useState("");
  const [marcada, setMarcada] = useState(0);
  const campo = useRef<HTMLInputElement>(null);
  const achadas = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    const todas = Array.isArray(lista.data?.automacoes) ? lista.data.automacoes : [];
    return termo ? todas.filter((a) => a.nome.toLowerCase().includes(termo) || (a.descricao ?? "").toLowerCase().includes(termo)) : todas;
  }, [lista.data, busca]);

  useEffect(() => { campo.current?.focus(); }, []);
  useEffect(() => { setMarcada(0); }, [busca]);

  function tecla(ev: React.KeyboardEvent) {
    // A marca nunca sai da lista (nem com a lista ainda carregando).
    if (ev.key === "ArrowDown") { ev.preventDefault(); setMarcada((m) => Math.max(0, Math.min(m + 1, achadas.length - 1))); }
    if (ev.key === "ArrowUp") { ev.preventDefault(); setMarcada((m) => Math.max(m - 1, 0)); }
    const escolhida = achadas[Math.min(marcada, achadas.length - 1)];
    if (ev.key === "Enter" && escolhida) { ev.preventDefault(); escolher({ id: escolhida.id, nome: escolhida.nome }); }
  }

  return (
    <Modal open onClose={fechar} title="Executar automação" className="max-w-xl"
      description="Só aparecem as automações que você pode executar. Setas para escolher, Enter para abrir.">
      <div className="space-y-3" data-testid="busca-executar">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input ref={campo} value={busca} onChange={(e) => setBusca(e.target.value)} onKeyDown={tecla}
            placeholder="Nome da automação" aria-label="Buscar automação para executar"
            className="h-12 w-full rounded-lg border border-input bg-background pl-11 pr-3 text-base" />
        </label>
        {!lista.data ? (
          <div className="skeleton h-40 rounded-lg" />
        ) : achadas.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-muted-foreground">
            {busca.trim() ? "Nada encontrado com esse nome." : "Você ainda não pode executar nenhuma automação."}
          </p>
        ) : (
          <ul className="max-h-80 divide-y divide-border overflow-y-auto rounded-lg border border-border" role="listbox" aria-label="Automações">
            {achadas.map((a, i) => (
              <li key={a.id} role="option" aria-selected={i === marcada}>
                <button onClick={() => escolher({ id: a.id, nome: a.nome })} onMouseEnter={() => setMarcada(i)}
                  className={cn("flex w-full items-center gap-3 px-4 py-3 text-left", i === marcada ? "bg-muted" : "hover:bg-muted")}>
                  <Play className="h-4 w-4 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-titulo">{a.nome}</span>
                    {a.descricao && <span className="block truncate text-sm text-muted-foreground">{a.descricao}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

/** As últimas automações que a pessoa vê, uma por automação (filtradas pela máquina escolhida nas abas do Painel). */
export function UltimasAutomacoes({ disparar, atualizar, maquina = "" }: {
  disparar: (d: Disparo) => void; atualizar: number; maquina?: string;
}) {
  const caminho = `/painel/recentes?limite=3${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ""}`;
  const recentes = useApi<Recentes>(caminho, { pollMs: 60000 });
  useEffect(() => { if (atualizar) void recentes.refetch(); }, [atualizar]); // eslint-disable-line react-hooks/exhaustive-deps

  // Resposta fora do formato não derruba o Painel: o bloco fica como "carregando".
  const dados = recentes.data && Array.isArray(recentes.data.automacoes) ? recentes.data : null;
  return (
    <section className="space-y-3" data-testid="ultimas-automacoes">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="titulo-condensado text-2xl">Últimas automações</h2>
        <Link href="/historico" className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
          <History className="h-4 w-4" /> Histórico
        </Link>
      </div>
      {!dados ? (
        <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-40 rounded-xl" />)}</div>
      ) : dados.automacoes.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-6 py-8 text-center text-muted-foreground">
          {maquina ? "Nenhuma automação rodou nesta máquina ainda." : "Nenhuma automação rodou ainda."}
        </p>
      ) : (
        <ul className="grid gap-4 md:grid-cols-3">
          {dados.automacoes.map((a) => <CartaoRecente key={a.automation_id} a={a} disparar={disparar} />)}
        </ul>
      )}
    </section>
  );
}

function CartaoRecente({ a, disparar }: { a: Recente; disparar: (d: Disparo) => void }) {
  const s = SITUACOES[a.ultima.status] ?? { texto: a.ultima.status, tom: "neutral" as const };
  const itens = a.ultima.itens;
  return (
    <li className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm" data-automacao={a.automation_id}>
      <div className="flex items-start justify-between gap-2">
        <Link href={`/automations/${a.automation_id}`} className="min-w-0 hover:underline">
          <p className="truncate text-lg font-semibold text-titulo">{a.automacao}</p>
        </Link>
        <Badge tone={s.tom} className="shrink-0">{s.texto}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        <Link href={`/execucoes/${a.ultima.execucao_id}`} className="hover:underline">{a.ultima.quando ? relativo(a.ultima.quando) : "—"}</Link>
        {a.ultima.maquinas.length > 0 && ` · ${a.ultima.maquinas.join(", ")}`}
      </p>
      <p className="truncate text-sm" title={itens.join(", ")}>
        {itens.length === 0 ? "sem itens" : `${itens.slice(0, 4).join(", ")}${itens.length > 4 ? ` e mais ${itens.length - 4}` : ""}`}
      </p>
      <div className="mt-auto flex flex-wrap gap-2">
        {a.pode_controlar && a.ultima.status === "cancelled" && !a.ultima.continuada_em && (
          <BotaoContinuar execucaoId={a.ultima.execucao_id} />
        )}
        {a.ultima.continuada_em && (
          <Link href={`/execucoes/${a.ultima.continuada_em}`} className="self-center text-sm font-medium text-primary hover:underline">
            Ver a continuação
          </Link>
        )}
        {a.pode_executar ? (
          <>
            <Button size="sm" onClick={() => disparar({ id: a.automation_id, nome: a.automacao })}>
              <Play className="h-4 w-4" /> Executar
            </Button>
            {itens.length > 0 && (
              <Button size="sm" variant="outline" onClick={() => disparar({ id: a.automation_id, nome: a.automacao, itens })}
                title="Abre a janela Executar com os mesmos itens marcados">
                <RotateCcw className="h-4 w-4" /> Repetir
              </Button>
            )}
          </>
        ) : (
          <span className="text-sm text-muted-foreground">Você só acompanha esta automação.</span>
        )}
      </div>
    </li>
  );
}
