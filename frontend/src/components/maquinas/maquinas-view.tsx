"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Copy, Plus, PlugZap, Settings2, Trash2 } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { useAvisos } from "@/hooks/use-avisos";
import { apiRequest } from "@/lib/api";
import { horario } from "@/lib/fila";
import type { BlocoNaLinha, LinhaDoTempo } from "@/lib/painel";
import { isAdminOrManager } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import type { Automation } from "@/types/automation";

type Instancia = {
  id: string;
  status: "pendente" | "aprovada" | "quarentena" | "revogada";
  automation_id: number;
  automacao: string | null;
  nome_informado: string | null;
  versao: string | null;
  maquina_id: string | null;
  maquina_nome: string | null;
  inscrita_em: string | null;
  ultimo_sinal: string | null;
};

const JANELAS = [
  { rotulo: "3 h", antes: 2, depois: 1 },
  { rotulo: "12 h", antes: 6, depois: 6 },
  { rotulo: "24 h", antes: 12, depois: 12 },
];

const CORES: Record<BlocoNaLinha["tipo"], string> = {
  feito: "bg-primary/70 hover:bg-primary",
  rodando: "bg-success hover:bg-success/90",
  previsto: "bg-nevoa/70 text-titulo hover:bg-nevoa",
};

export function MaquinasView() {
  const { user } = useAuth();
  const gestor = isAdminOrManager(user);
  const [janela, setJanela] = useState(JANELAS[1]);
  const [opcoes, setOpcoes] = useState(false);
  const caminho = `/painel/linha-do-tempo?horas_antes=${janela.antes}&horas_depois=${janela.depois}`;
  const linha = useApi<LinhaDoTempo>(caminho, { pollMs: 60000 });
  const aoVivo = useAvisos("/painel/avisos", () => void linha.refetch(), 1500);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Monitorar</p>
          <h1 className="titulo-condensado text-4xl">Máquinas</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-border bg-card p-1" aria-label="Janela da linha do tempo">
            {JANELAS.map((j) => (
              <button key={j.rotulo} onClick={() => setJanela(j)} aria-pressed={janela === j}
                className={cn("rounded-md px-3 py-1.5 text-sm font-medium",
                  janela === j ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
                {j.rotulo}
              </button>
            ))}
          </div>
          {gestor && (
            <Button variant="outline" onClick={() => setOpcoes((v) => !v)} aria-expanded={opcoes}>
              <Settings2 className="h-4 w-4" /> Gerenciar
            </Button>
          )}
        </div>
      </div>

      {opcoes && gestor && <Gerenciar mudou={() => void linha.refetch()} />}

      {linha.error && !linha.data ? (
        <ErrorState message={linha.error} onRetry={() => void linha.refetch()} />
      ) : !linha.data ? (
        <div className="skeleton h-80 w-full rounded-xl" />
      ) : (
        <Gantt dados={linha.data} aoVivo={aoVivo} />
      )}

      {gestor && <Instancias />}
    </div>
  );
}

/** Largura de uma hora na linha do tempo: janela longa rola na horizontal em vez de espremer. */
const HORA_REM = 5;

function rotuloDoDia(iso: string, agora: Date): string {
  const d = new Date(iso);
  const dia = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dias = Math.round((dia(d) - dia(agora)) / 86_400_000);
  if (dias === 0) return "hoje";
  if (dias === 1) return "amanhã";
  if (dias === -1) return "ontem";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function Gantt({ dados, aoVivo }: { dados: LinhaDoTempo; aoVivo: boolean }) {
  const rolagem = useRef<HTMLDivElement>(null);
  const horas = Math.max((Date.parse(dados.fim) - Date.parse(dados.inicio)) / 3_600_000, 1);

  // Ao abrir (ou trocar a janela), deixa o "agora" a um terço da área visível.
  useEffect(() => {
    const caixa = rolagem.current;
    const linhaAgora = caixa?.querySelector<HTMLElement>("[data-agora]");
    if (!caixa || !linhaAgora) return;
    const desvio = linhaAgora.getBoundingClientRect().left - caixa.getBoundingClientRect().left;
    caixa.scrollLeft += desvio - caixa.clientWidth / 3;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [horas, dados.maquinas.length]);

  if (dados.maquinas.length === 0) {
    return <p className="rounded-xl border border-dashed border-border px-6 py-12 text-center text-muted-foreground">Nenhuma máquina cadastrada.</p>;
  }
  const agora = new Date(dados.agora);
  const marcas = dados.marcas.map((m, i) => {
    const dia = new Date(m.quando).toDateString();
    const virou = i > 0 && dia !== new Date(dados.marcas[i - 1].quando).toDateString();
    return { ...m, hora: new Date(m.quando).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }), dia: virou ? rotuloDoDia(m.quando, agora) : null };
  });
  const trilhoRem = horas * HORA_REM;
  // janela curta ocupa a largura toda; longa passa da tela e rola
  const colunas = { gridTemplateColumns: `10rem minmax(${trilhoRem}rem, 1fr)` };
  return (
    <section className="rounded-xl border border-border bg-card shadow-sm" data-testid="linha-do-tempo">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 text-sm text-muted-foreground">
        <span className="flex items-center gap-4">
          <Legenda cor="bg-primary/70" texto="Concluído" />
          <Legenda cor="bg-success" texto="Rodando" />
          <Legenda cor="bg-nevoa/70" texto="Previsto" />
        </span>
        <span>{aoVivo ? "Atualiza sozinha" : "Relendo a cada minuto"}</span>
      </div>
      <div ref={rolagem} className="overflow-x-auto pb-4 pt-3" data-testid="linha-do-tempo-rolagem">
        <div className="grid gap-x-4 pr-5" style={colunas}>
          <div className="sticky left-0 z-20 bg-card" />
          <div className="relative mb-2 h-10 border-b border-border text-xs text-muted-foreground">
            {marcas.map((m) => (
              <span key={m.quando} className="tabular absolute bottom-1 -translate-x-1/2 whitespace-nowrap text-center" style={{ left: `${m.posicao}%` }}>
                {m.dia && <span className="block font-sans text-xs font-semibold uppercase tracking-wider text-primary">{m.dia}</span>}
                {m.hora}
              </span>
            ))}
          </div>
          {dados.maquinas.map((m) => (
            <div key={m.maquina_id} className="contents">
              <p className="sticky left-0 z-20 truncate bg-card py-3 pl-5 font-semibold text-titulo" title={m.nome}>{m.nome}</p>
              <div className="relative my-2 h-10 rounded-md bg-muted">
                {marcas.map((marca) => (
                  <span key={marca.quando} className={cn("absolute inset-y-0 w-px", marca.dia ? "bg-primary/40" : "bg-border")} style={{ left: `${marca.posicao}%` }} />
                ))}
                <span data-agora className="absolute inset-y-[-0.5rem] z-10 w-0.5 bg-destructive" style={{ left: `${dados.agora_posicao}%` }} title="Agora" />
                {m.blocos.map((b, i) => (
                  <BlocoDesenhado key={`${b.job_id}-${b.tipo}-${i}`} b={b} trilhoRem={trilhoRem} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BlocoDesenhado({ b, trilhoRem }: { b: BlocoNaLinha; trilhoRem: number }) {
  const titulo = [
    b.automacao ?? "Job de outra automação",
    b.itens.length ? `itens ${b.itens.slice(0, 5).join(", ")}${b.itens.length > 5 ? "…" : ""}` : null,
    `${horario(b.inicio)} → ${b.fim ? horario(b.fim) : b.tipo === "rodando" ? "sem previsão" : "sem previsão de término"}`,
  ].filter(Boolean).join(" · ");
  const classe = cn("absolute inset-y-1 flex items-center overflow-hidden rounded px-2 text-xs font-medium text-white transition-colors",
    CORES[b.tipo], !b.fim_conhecido && "border-2 border-dashed border-white/70");
  const estilo = { left: `${b.esquerda}%`, width: `${b.largura}%` };
  const texto = (b.largura / 100) * trilhoRem > 4 ? <span className="truncate">{b.automacao ?? "Ocupada"}</span> : null;
  return b.execucao_id ? (
    <Link href={`/execucoes/${b.execucao_id}`} className={classe} style={estilo} title={titulo}>{texto}</Link>
  ) : (
    <span className={classe} style={estilo} title={titulo}>{texto}</span>
  );
}

function Legenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn("h-3 w-5 rounded-sm", cor)} />
      {texto}
    </span>
  );
}

type Vinculos = {
  maquina: { id: string; nome: string };
  automacoes: Array<{ instancia_id: string; automation_id: number; automacao: string | null; situacao: string }>;
  agents: Array<{ id: string; nome: string }>;
  fila: number;
  rodando: number;
};

function Gerenciar({ mudou }: { mudou: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const automacoes = useApi<Automation[]>("/automations");
  const maquinas = useApi<{ maquinas: Array<{ id: string; nome: string; status: string }> }>("/maquinas");
  const [apagando, setApagando] = useState<{ id: string; nome: string } | null>(null);
  const [nome, setNome] = useState("");
  const [automacao, setAutomacao] = useState("");
  const [codigo, setCodigo] = useState<{ codigo: string; expira_em: string } | null>(null);

  async function cadastrar() {
    try {
      await apiRequest("/maquinas", { method: "POST", token, body: JSON.stringify({ nome }) });
      toast({ title: `Máquina ${nome} cadastrada`, kind: "success" });
      setNome("");
      await maquinas.refetch();
      mudou();
    } catch (err) {
      toast({ title: "Não foi possível cadastrar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function gerarCodigo() {
    try {
      setCodigo(await apiRequest(`/automations/${automacao}/instancias-diretas/codigos`, { method: "POST", token }));
    } catch (err) {
      toast({ title: "Não foi possível gerar o código", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <section className="grid gap-4 rounded-xl border border-border bg-card p-5 shadow-sm lg:grid-cols-2">
      <div className="space-y-3">
        <p className="font-semibold text-titulo">Cadastrar máquina</p>
        <p className="text-sm text-muted-foreground">Máquina sem Agent também entra aqui; depois você aprova nela as automações diretas.</p>
        <div className="flex gap-2">
          <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Nome, como MAQ194"
            className="h-11 flex-1 rounded-md border border-input bg-background px-3" aria-label="Nome da máquina" />
          <Button onClick={() => void cadastrar()} disabled={nome.trim().length < 2}>
            <Plus className="h-4 w-4" /> Cadastrar
          </Button>
        </div>
      </div>
      <div className="space-y-3">
        <p className="font-semibold text-titulo">Conectar uma automação direta</p>
        <p className="text-sm text-muted-foreground">Gera um código de uso único, válido por 30 minutos, para a automação se inscrever pela máquina.</p>
        <div className="flex gap-2">
          <select value={automacao} onChange={(e) => setAutomacao(e.target.value)}
            className="h-11 flex-1 rounded-md border border-input bg-background px-3" aria-label="Automação">
            <option value="">Escolha a automação…</option>
            {(automacoes.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <Button onClick={() => void gerarCodigo()} disabled={!automacao}>
            <PlugZap className="h-4 w-4" /> Gerar código
          </Button>
        </div>
      </div>
      <div className="space-y-3 lg:col-span-2" data-testid="maquinas-cadastradas">
        <p className="font-semibold text-titulo">Máquinas cadastradas</p>
        {(maquinas.data?.maquinas ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma máquina cadastrada.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {(maquinas.data?.maquinas ?? []).map((m) => (
              <li key={m.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="min-w-0 flex-1 truncate font-medium">{m.nome}</span>
                {m.status !== "ativa" && <span className="text-sm text-muted-foreground">{m.status}</span>}
                <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setApagando(m)} aria-label={`Apagar ${m.nome}`}>
                  <Trash2 className="h-4 w-4" /> Apagar
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {apagando && (
        <ApagarMaquina maquina={apagando} fechar={() => setApagando(null)}
          apagada={() => { setApagando(null); void maquinas.refetch(); mudou(); }} />
      )}
      <Modal open={codigo !== null} onClose={() => setCodigo(null)} title="Código de inscrição"
        description="Aparece só agora. Use na máquina, no comando de inscrição do SDK.">
        {codigo && (
          <div className="space-y-3 text-center">
            <p className="titulo-condensado select-all text-4xl tracking-widest text-titulo">{codigo.codigo}</p>
            <p className="text-sm text-muted-foreground">Vale até {horario(codigo.expira_em)} e só uma vez.</p>
            <Button variant="outline" onClick={() => void navigator.clipboard?.writeText(codigo.codigo)}>
              <Copy className="h-4 w-4" /> Copiar
            </Button>
          </div>
        )}
      </Modal>
    </section>
  );
}

/** Confirmação de apagar: mostra o que depende da máquina antes; com execução rodando, não deixa. */
function ApagarMaquina({ maquina, fechar, apagada }: { maquina: { id: string; nome: string }; fechar: () => void; apagada: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const vinculos = useApi<Vinculos>(`/maquinas/${maquina.id}/vinculos`);
  const [apagando, setApagando] = useState(false);
  const v = vinculos.data;
  const temVinculo = !!v && (v.automacoes.length > 0 || v.agents.length > 0 || v.fila > 0);

  async function apagar() {
    setApagando(true);
    try {
      await apiRequest(`/maquinas/${maquina.id}${temVinculo ? "?confirmar=true" : ""}`, { method: "DELETE", token });
      toast({ title: `Máquina ${maquina.nome} apagada`, kind: "success" });
      apagada();
    } catch (err) {
      toast({ title: "Não foi possível apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
      void vinculos.refetch();
    } finally {
      setApagando(false);
    }
  }

  return (
    <Modal open onClose={fechar} title={`Apagar ${maquina.nome}`} className="max-w-xl"
      description="A máquina sai do cadastro, das telas e da fila. O histórico das execuções que rodaram nela continua com o nome."
      footer={<>
        <Button variant="ghost" onClick={fechar}>Cancelar</Button>
        <Button variant="destructive" onClick={() => void apagar()} disabled={!v || v.rodando > 0 || apagando}>
          {apagando ? "Apagando…" : temVinculo ? "Apagar mesmo assim" : "Apagar"}
        </Button>
      </>}>
      <div className="space-y-4" data-testid="apagar-maquina">
        {!v ? <div className="skeleton h-24 rounded-lg" /> : v.rodando > 0 ? (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
            {v.rodando} execução(ões) rodando nesta máquina agora. Espere terminar (ou pare a execução) para apagar.
          </p>
        ) : !temVinculo ? (
          <p className="text-sm">Nenhuma automação, Agent ou pedido da fila depende desta máquina.</p>
        ) : (
          <>
            <p role="alert" className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <span>Isto depende desta máquina. Ao apagar, as automações ficam <strong>sem máquina</strong>: voltam a esperar
                aprovação em Automações diretas, onde você escolhe outra máquina.</span>
            </p>
            {v.automacoes.length > 0 && (
              <div>
                <p className="text-sm font-medium">Automações ({v.automacoes.length})</p>
                <ul className="mt-1 list-disc pl-5 text-sm">
                  {v.automacoes.map((a) => <li key={a.instancia_id}>{a.automacao ?? `Automação ${a.automation_id}`} <span className="text-muted-foreground">({a.situacao})</span></li>)}
                </ul>
              </div>
            )}
            {v.agents.length > 0 && (
              <div>
                <p className="text-sm font-medium">Agents ({v.agents.length})</p>
                <ul className="mt-1 list-disc pl-5 text-sm">{v.agents.map((a) => <li key={a.id}>{a.nome}</li>)}</ul>
                <p className="mt-1 text-xs text-muted-foreground">O Agent fica sem máquina e não recebe trabalho até ser ligado a outra.</p>
              </div>
            )}
            {v.fila > 0 && (
              <p className="text-sm"><span className="font-medium">Na fila:</span> {v.fila} pedido(s) marcados para rodar só nesta
                máquina. Passam a poder rodar em qualquer máquina que sirva.</p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

const SITUACAO: Record<Instancia["status"], { texto: string; cor: string }> = {
  pendente: { texto: "Aguardando aprovação", cor: "text-warning" },
  aprovada: { texto: "Aprovada", cor: "text-success" },
  quarentena: { texto: "Em quarentena", cor: "text-warning" },
  revogada: { texto: "Revogada", cor: "text-muted-foreground" },
};

function Instancias() {
  const { token } = useAuth();
  const { toast } = useToast();
  const lista = useApi<{ instancias: Instancia[] }>("/instancias-diretas");
  const maquinas = useApi<{ maquinas: Array<{ id: string; nome: string }> }>("/maquinas");
  const [escolhida, setEscolhida] = useState<Record<string, string>>({});
  const instancias = lista.data?.instancias ?? [];
  if (instancias.length === 0) return null;

  async function decidir(i: Instancia, acao: "aprovar" | "quarentena" | "revogar") {
    try {
      await apiRequest(`/instancias-diretas/${i.id}/${acao}`, { method: "POST", token,
        body: JSON.stringify(acao === "aprovar" ? { maquina_id: escolhida[i.id] } : {}) });
      toast({ title: acao === "aprovar" ? "Instância aprovada" : acao === "quarentena" ? "Em quarentena" : "Instância revogada", kind: "success" });
      await lista.refetch();
    } catch (err) {
      toast({ title: "Não foi possível", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="titulo-condensado text-2xl">Automações diretas</h2>
      <div className="divide-y divide-border rounded-xl border border-border bg-card shadow-sm">
        {instancias.map((i) => (
          <div key={i.id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
            <div className="min-w-0">
              <p className="font-semibold text-titulo">{i.automacao ?? "Automação"} <span className="font-normal text-muted-foreground">· {i.maquina_nome ?? i.nome_informado ?? "máquina não escolhida"}</span></p>
              <p className={cn("text-sm", SITUACAO[i.status].cor)}>
                {SITUACAO[i.status].texto}
                {i.ultimo_sinal && <span className="text-muted-foreground"> · último sinal {horario(i.ultimo_sinal)}</span>}
              </p>
            </div>
            {i.status !== "revogada" && (
              <div className="flex flex-wrap items-center gap-2">
                {(i.status === "pendente" || i.status === "quarentena") && (
                  <>
                    <select value={escolhida[i.id] ?? ""} onChange={(e) => setEscolhida((p) => ({ ...p, [i.id]: e.target.value }))}
                      className="h-10 rounded-md border border-input bg-background px-3" aria-label="Máquina da instância">
                      <option value="">Em qual máquina?</option>
                      {(maquinas.data?.maquinas ?? []).map((m) => <option key={m.id} value={m.id}>{m.nome}</option>)}
                    </select>
                    <Button size="sm" onClick={() => void decidir(i, "aprovar")} disabled={!escolhida[i.id]}>Aprovar</Button>
                  </>
                )}
                {i.status === "aprovada" && (
                  <Button size="sm" variant="outline" onClick={() => void decidir(i, "quarentena")}>Quarentena</Button>
                )}
                <Button size="sm" variant="ghost" className="text-destructive" onClick={() => void decidir(i, "revogar")}>Revogar</Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
