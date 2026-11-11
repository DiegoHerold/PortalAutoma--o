"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  ChevronDown,
  ChevronUp,
  Clock,
  HelpCircle,
  ListOrdered,
  Monitor,
  MonitorOff,
  RefreshCw,
  RotateCcw,
  Play,
  Server,
} from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { abrirStream } from "@/lib/stream";
import {
  duracao,
  horario,
  relativo,
  rotuloItem,
  POOLS,
  type JobNaFila,
  type JobPerdido,
  type MaquinaNaFila,
  type VisaoFila,
} from "@/lib/fila";
import { cn } from "@/lib/utils";
import { PageTitle } from "@/components/shared/page-title";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

/** A fila é relida quando o portal avisa que ela mudou (LISTEN/NOTIFY) e, por segurança, a cada 30 s. */
const RELEITURA_MS = 30000;

type Confirmacao = {
  titulo: string;
  efeito: string[];
  botao: string;
  perigo?: boolean;
  executar: () => Promise<void>;
};

export function FilaManager() {
  const { token } = useAuth();
  const { data, loading, error, refetch } = useApi<VisaoFila>("/fila", { pollMs: RELEITURA_MS });
  const [aoVivo, setAoVivo] = useState(false);
  const releitura = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!token) return;
    const fechar = abrirStream(
      "/fila/avisos",
      token,
      (evento) => {
        if (evento.evento !== "mudou" || releitura.current) return;
        // Vários avisos seguidos viram uma releitura só.
        releitura.current = setTimeout(() => {
          releitura.current = null;
          void refetch();
        }, 300);
      },
      { aoMudarConexao: setAoVivo },
    );
    return () => {
      fechar();
      if (releitura.current) clearTimeout(releitura.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  const { toast } = useToast();
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);

  async function agir(chave: string, caminho: string, metodo: "POST" | "PATCH", corpo: unknown, sucesso: string) {
    setOcupado(chave);
    try {
      await apiRequest(caminho, { method: metodo, body: JSON.stringify(corpo), token });
      toast({ title: sucesso, kind: "success" });
      await refetch();
    } catch (err) {
      toast({ title: "Não foi possível concluir", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setOcupado(null);
    }
  }

  const agora = data ? new Date(data.gerado_em) : new Date();

  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Operação"
        title="Fila"
        description="Quem espera, em qual máquina deve rodar, quando começa, quando termina e por que ainda não começou."
        actions={
          <div className="flex items-center gap-3">
            {data && (
              <span
                className="flex items-center gap-1.5 text-xs text-muted-foreground"
                title={aoVivo ? "Atualiza sozinha quando a fila muda" : "Sem conexão ao vivo: relendo a cada 30 segundos"}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", aoVivo ? "animate-pulse-dot bg-success" : "bg-warning")} />
                Atualizada às {new Date(data.gerado_em).toLocaleTimeString("pt-BR")}
              </span>
            )}
            <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={loading}>
              <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} /> Atualizar
            </Button>
          </div>
        }
      />

      {error && !data ? (
        <ErrorState message={error} onRetry={() => void refetch()} />
      ) : !data ? (
        <CarregandoFila />
      ) : (
        <>
          <Resumo visao={data} agora={agora} />
          {data.perdidos.length > 0 && (
            <Perdidos
              perdidos={data.perdidos}
              ocupado={ocupado}
              pedir={(job, decisao) =>
                setConfirmacao(confirmarDecisao(job, decisao, () =>
                  agir(job.job_id, `/fila/jobs/${job.job_id}/decisao`, "POST", { decisao },
                    decisao === "continuar" ? "Job devolvido à fila para continuar" : "Job devolvido à fila do início"),
                ))
              }
            />
          )}
          <Maquinas maquinas={data.maquinas} />
          <ListaDeJobs
            jobs={data.jobs}
            agora={agora}
            ocupado={ocupado}
            prioridade={(job, valor) =>
              void agir(job.job_id, `/fila/jobs/${job.job_id}`, "PATCH", { prioridade: valor }, `Prioridade ajustada para ${valor}`)
            }
            cancelar={(job) =>
              setConfirmacao({
                titulo: "Cancelar este job?",
                efeito: [
                  `${job.automacao ?? "A automação"} não vai rodar para ${job.itens.length === 1 ? "o item" : "os itens"} ${job.itens.join(", ")}.`,
                  "O job ainda não começou, então nada é desfeito em nenhuma máquina.",
                  "Para rodar depois, é preciso pedir a execução de novo.",
                ],
                botao: "Cancelar job",
                perigo: true,
                executar: () => agir(job.job_id, `/fila/jobs/${job.job_id}/cancelar`, "POST", {}, "Job cancelado"),
              })
            }
          />
        </>
      )}

      <Modal
        open={confirmacao !== null}
        onClose={() => setConfirmacao(null)}
        title={confirmacao?.titulo}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmacao(null)}>
              Voltar
            </Button>
            <Button
              variant={confirmacao?.perigo ? "destructive" : "primary"}
              onClick={async () => {
                const acao = confirmacao;
                setConfirmacao(null);
                await acao?.executar();
              }}
            >
              {confirmacao?.botao}
            </Button>
          </>
        }
      >
        <p className="eyebrow mb-3">O que acontece</p>
        <ul className="space-y-2 text-sm">
          {confirmacao?.efeito.map((linha) => (
            <li key={linha} className="flex gap-2">
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <span>{linha}</span>
            </li>
          ))}
        </ul>
      </Modal>
    </div>
  );
}

function confirmarDecisao(job: JobPerdido, decisao: "continuar" | "recomecar", executar: () => Promise<void>): Confirmacao {
  const maquina = job.maquina_nome ?? "a mesma máquina";
  if (decisao === "continuar") {
    return {
      titulo: "Continuar de onde parou?",
      efeito: [
        job.estado_central
          ? "O job volta para a fila e retoma do último ponto registrado, em qualquer máquina compatível: o progresso desta automação fica guardado fora da máquina."
          : `O job volta para a fila e retoma do último ponto registrado, só em ${maquina}, porque o progresso ficou nela. Enquanto ela não voltar, o job espera.`,
        `A tela de ${maquina} é liberada para a fila.`,
        "Antes, confira na máquina se a automação não ficou parada no meio de uma tela.",
      ],
      botao: "Continuar",
      executar,
    };
  }
  return {
    titulo: "Recomeçar do zero?",
    efeito: [
      "O progresso registrado deste job é descartado e ele volta para a fila desde o início, para qualquer máquina compatível.",
      "Itens que já tinham sido feitos serão feitos de novo. Confira se isso não duplica lançamentos.",
      `A tela de ${maquina} é liberada para a fila.`,
    ],
    botao: "Recomeçar do zero",
    perigo: true,
    executar,
  };
}

function CarregandoFila() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Carregando a fila">
      <div className="skeleton h-28 w-full rounded-xl" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div className="skeleton h-32" />
        <div className="skeleton h-32" />
        <div className="skeleton h-32" />
      </div>
      <div className="skeleton h-64 w-full" />
    </div>
  );
}

function Resumo({ visao, agora }: { visao: VisaoFila; agora: Date }) {
  const livres = visao.maquinas.filter((m) => m.online && !m.sessao_bloqueada && !m.job_perdido && m.vagas_tela > 0).length;
  const terminos = visao.jobs.map((j) => j.termino_previsto);
  const fim = terminos.length > 0 && terminos.every(Boolean) ? terminos.reduce((a, b) => (a! > b! ? a : b)) : null;
  const semPrevisao = visao.jobs.filter((j) => !j.termino_previsto).length;

  return (
    <section className="faixa-noite overflow-hidden rounded-xl shadow-md">
      <dl className="grid grid-cols-2 divide-[hsl(var(--faixa-divisao))] lg:grid-cols-4 lg:divide-x">
        <Numero rotulo="Esperando" valor={String(visao.jobs.length)} detalhe={visao.jobs.length === 1 ? "job na fila" : "jobs na fila"} />
        <Numero rotulo="Telas livres" valor={`${livres}/${visao.maquinas.length}`} detalhe="máquinas prontas para receber" />
        <Numero
          rotulo="Fila termina"
          valor={visao.jobs.length === 0 ? "—" : fim ? horario(fim, agora) : "Sem previsão"}
          detalhe={
            visao.jobs.length === 0
              ? "nada esperando"
              : fim
                ? relativo(fim, agora)
                : `${semPrevisao} ${semPrevisao === 1 ? "job" : "jobs"} sem previsão — veja o motivo em cada um`
          }
        />
        <Numero
          rotulo="Perdidos"
          valor={String(visao.perdidos.length)}
          detalhe={visao.perdidos.length ? "aguardando sua decisão" : "nenhum"}
          alerta={visao.perdidos.length > 0}
        />
      </dl>
    </section>
  );
}

function Numero({ rotulo, valor, detalhe, alerta }: { rotulo: string; valor: string; detalhe: string; alerta?: boolean }) {
  return (
    <div className="px-5 py-4">
      <dt className="text-xs font-bold uppercase tracking-[0.16em] faixa-rotulo">{rotulo}</dt>
      <dd className={cn("titulo-condensado mt-1 text-3xl leading-none", alerta ? "faixa-alerta" : "faixa-valor")}>{valor}</dd>
      <dd className="mt-1.5 text-xs faixa-apoio">{detalhe}</dd>
    </div>
  );
}

function Perdidos({
  perdidos,
  ocupado,
  pedir,
}: {
  perdidos: JobPerdido[];
  ocupado: string | null;
  pedir: (job: JobPerdido, decisao: "continuar" | "recomecar") => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-warning" />
        <h2 className="titulo-condensado text-xl">Jobs perdidos</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        A máquina parou de responder no meio destes jobs. Eles não voltam para a fila sozinhos: automação de tela pode ter
        ficado no meio de um lançamento. Decida cada um.
      </p>
      <div className="grid gap-3 lg:grid-cols-2">
        {perdidos.map((job) => (
          <article key={job.job_id} className="rounded-lg border border-warning/40 bg-warning/5 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-titulo">{job.automacao ?? "Automação"}</p>
                <p className="text-xs text-muted-foreground">
                  {job.maquina_nome ?? "Máquina desconhecida"}
                  {job.perdido_em ? ` · perdido às ${horario(job.perdido_em)}` : ""}
                </p>
              </div>
              <Badge tone="warning">Aguardando decisão</Badge>
            </div>
            {job.itens.length > 0 && <Itens itens={job.itens.map(rotuloItem)} className="mt-3" />}
            {job.motivo && <p className="mt-2 text-sm">{job.motivo}</p>}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => pedir(job, "continuar")} disabled={ocupado === job.job_id}>
                <Play className="h-3.5 w-3.5" /> Continuar
              </Button>
              <Button size="sm" variant="outline" onClick={() => pedir(job, "recomecar")} disabled={ocupado === job.job_id}>
                <RotateCcw className="h-3.5 w-3.5" /> Recomeçar do zero
              </Button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function Maquinas({ maquinas }: { maquinas: MaquinaNaFila[] }) {
  return (
    <section className="space-y-3">
      <h2 className="titulo-condensado text-xl">Máquinas</h2>
      {maquinas.length === 0 ? (
        <EmptyState
          icon={Server}
          title="Nenhuma máquina disponível para a fila"
          description="Cadastre a máquina e conecte um Agent ou uma instância direta aprovada para que os jobs tenham onde rodar."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {maquinas.map((m) => (
            <CartaoMaquina key={m.id} maquina={m} />
          ))}
        </div>
      )}
    </section>
  );
}

function CartaoMaquina({ maquina }: { maquina: MaquinaNaFila }) {
  const situacao = !maquina.online
    ? { texto: "Sem sinal", tom: "destructive" as const }
    : maquina.job_perdido
      ? { texto: "Job perdido", tom: "warning" as const }
      : maquina.sessao_bloqueada
        ? { texto: "Sessão bloqueada", tom: "warning" as const }
        : { texto: "Online", tom: "success" as const };
  const telaLivre = maquina.vagas_tela > 0 && maquina.online && !maquina.sessao_bloqueada && !maquina.job_perdido;
  const Tela = telaLivre ? Monitor : MonitorOff;

  return (
    <article className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold text-titulo">{maquina.nome ?? maquina.id}</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Tela className={cn("h-3.5 w-3.5", telaLivre ? "text-success" : "text-muted-foreground")} />
            {telaLivre ? "Tela livre" : "Tela ocupada"}
          </p>
        </div>
        <Badge tone={situacao.tom}>
          <span className={cn("h-1.5 w-1.5 rounded-full bg-current", situacao.tom === "success" && "animate-pulse-dot")} />
          {situacao.texto}
        </Badge>
      </div>
      <div className="mt-3 space-y-1.5 border-t border-border pt-3">
        {maquina.rodando.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nada rodando agora.</p>
        ) : (
          maquina.rodando.map((r, i) => (
            <div key={r.job_id ?? i} className="flex items-center justify-between gap-2 text-sm">
              <span className="text-muted-foreground">{POOLS[r.pool] ?? r.pool}</span>
              <span
                className={cn(
                  "inline-block text-right text-xs first-letter:uppercase",
                  r.restante_s == null ? "text-warning" : "font-semibold text-titulo",
                )}
              >
                {r.restante_s != null && r.restante_s > 0
                  ? `termina ${duracao(r.restante_s)}`
                  : (r.motivo ?? "sem previsão de término")}
              </span>
            </div>
          ))
        )}
      </div>
    </article>
  );
}

function ListaDeJobs({
  jobs,
  agora,
  ocupado,
  prioridade,
  cancelar,
}: {
  jobs: JobNaFila[];
  agora: Date;
  ocupado: string | null;
  prioridade: (job: JobNaFila, valor: number) => void;
  cancelar: (job: JobNaFila) => void;
}) {
  return (
    <section className="space-y-3">
      <h2 className="titulo-condensado text-xl">Esperando</h2>
      {jobs.length === 0 ? (
        <EmptyState
          icon={ListOrdered}
          title="Fila vazia"
          description="Nenhum job esperando. Cada pedido de execução aparece aqui com a máquina prevista, o horário estimado e o motivo da espera."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <div className="hidden grid-cols-[3rem_minmax(0,2.2fr)_minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(0,1fr)_7rem_5.5rem] gap-4 border-b border-border bg-muted px-4 py-2.5 text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground lg:grid">
            <span>Pos.</span>
            <span>Automação e itens</span>
            <span>Máquina prevista</span>
            <span>Início → término</span>
            <span>Estimativa</span>
            <span>Prioridade</span>
            <span className="sr-only">Ações</span>
          </div>
          <ol className="divide-y divide-border">
            {jobs.map((job) => (
              <LinhaJob
                key={job.job_id}
                job={job}
                agora={agora}
                ocupado={ocupado === job.job_id}
                prioridade={prioridade}
                cancelar={cancelar}
              />
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function LinhaJob({
  job,
  agora,
  ocupado,
  prioridade,
  cancelar,
}: {
  job: JobNaFila;
  agora: Date;
  ocupado: boolean;
  prioridade: (job: JobNaFila, valor: number) => void;
  cancelar: (job: JobNaFila) => void;
}) {
  const [explicar, setExplicar] = useState(false);
  const semPrevisao = job.inicio_previsto == null || job.estimativa_s == null;

  return (
    <li className="px-4 py-3.5" data-testid="job-na-fila">
      <div className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-3 gap-y-3 lg:grid-cols-[3rem_minmax(0,2.2fr)_minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(0,1fr)_7rem_5.5rem] lg:items-center lg:gap-4">
        <span className="titulo-condensado row-span-2 flex h-9 w-9 items-center justify-center rounded-md bg-secondary text-lg text-titulo lg:row-span-1">
          {job.posicao}
        </span>

        <div className="min-w-0">
          <p className="truncate font-semibold text-titulo">{job.automacao ?? "Automação"}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge tone="outline" className="py-0 text-xs">
              {POOLS[job.pool] ?? job.pool}
            </Badge>
            <Itens itens={job.itens} />
          </div>
        </div>

        <div className="col-start-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:col-span-4 lg:col-start-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(0,1fr)_7rem] lg:gap-4">
          <Campo rotulo="Máquina prevista">
            <span className="flex items-center gap-1.5">
              {job.maquina_prevista_nome ?? <span className="text-muted-foreground">—</span>}
              {job.maquina_obrigatoria && (
                <Badge tone="info" className="px-1.5 py-0 text-xs" title="Retomada de job perdido: só roda nesta máquina">
                  fixa
                </Badge>
              )}
            </span>
          </Campo>
          <Campo rotulo="Início → término">
            {job.inicio_previsto ? (
              <span className="tabular text-[0.8125rem]">
                {horario(job.inicio_previsto, agora)}
                <ArrowRight className="mx-1 inline h-3 w-3 text-muted-foreground" />
                {job.termino_previsto ? horario(job.termino_previsto, agora) : "?"}
                <span className="block font-sans text-xs text-muted-foreground">começa {relativo(job.inicio_previsto, agora)}</span>
              </span>
            ) : (
              <span className="font-medium text-warning">Sem previsão</span>
            )}
          </Campo>
          <Campo rotulo="Estimativa">
            {job.estimativa_s != null ? (
              <span className="titulo-condensado text-lg leading-none">{duracao(job.estimativa_s)}</span>
            ) : job.estimativa_minima_s != null ? (
              <span className="text-[0.8125rem]">
                pelo menos <span className="titulo-condensado text-lg leading-none">{duracao(job.estimativa_minima_s)}</span>
              </span>
            ) : (
              <span className="font-medium text-warning">Sem previsão</span>
            )}
          </Campo>
          <Campo rotulo="Prioridade">
            <span className="inline-flex items-center rounded-md border border-input">
              <button
                className="px-1.5 py-1 text-muted-foreground hover:text-foreground disabled:opacity-40"
                onClick={() => prioridade(job, job.prioridade - 1)}
                disabled={ocupado}
                aria-label="Baixar prioridade"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
              <span className="tabular min-w-[2ch] text-center text-sm">{job.prioridade}</span>
              <button
                className="px-1.5 py-1 text-muted-foreground hover:text-foreground disabled:opacity-40"
                onClick={() => prioridade(job, job.prioridade + 1)}
                disabled={ocupado}
                aria-label="Subir prioridade"
              >
                <ChevronUp className="h-4 w-4" />
              </button>
            </span>
          </Campo>
        </div>

        <div className="col-start-2 flex gap-1 lg:col-start-auto lg:justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExplicar((v) => !v)}
            aria-expanded={explicar}
            title="Por que espera"
            className="px-2"
          >
            <HelpCircle className="h-4 w-4" />
            <span className="lg:sr-only">Por que espera</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => cancelar(job)}
            disabled={ocupado}
            title="Cancelar job"
            className="px-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            <Ban className="h-4 w-4" />
            <span className="lg:sr-only">Cancelar</span>
          </Button>
        </div>
      </div>

      {(semPrevisao || job.motivos.length > 0) && (
        <ul className="mt-3 space-y-1 rounded-md bg-warning/10 px-3 py-2 text-[0.8125rem] lg:ml-[4rem]">
          {job.motivos.length === 0 && (
            <li className="flex gap-2">
              <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
              <span>Sem previsão, e o portal não informou o motivo. Isso é um defeito: avise o administrador.</span>
            </li>
          )}
          {job.motivos.map((m) => (
            <li key={m.codigo} className="flex gap-2">
              <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
              <span className="block first-letter:uppercase">{m.texto}</span>
            </li>
          ))}
          {job.etapas_sem_base.length > 0 && (
            <li className="pl-5 text-xs text-muted-foreground">Etapas sem histórico: {job.etapas_sem_base.join(", ")}</li>
          )}
        </ul>
      )}

      {explicar && (
        <div className="mt-3 rounded-md border border-border bg-muted px-3 py-2 text-[0.8125rem] lg:ml-[4rem]">
          <p className="eyebrow mb-1.5 text-xs">Por que espera</p>
          <PorQueEspera job={job} agora={agora} />
        </div>
      )}
    </li>
  );
}

function PorQueEspera({ job, agora }: { job: JobNaFila; agora: Date }) {
  const frases: string[] = [];
  frases.push(
    `Está em ${job.posicao}º na fila: prioridade ${job.prioridade}` +
      (job.posicao_manual != null ? `, posição manual ${job.posicao_manual}` : "") +
      `, pedido às ${horario(job.enfileirado_em, agora)}.`,
  );
  if (job.maquina_obrigatoria) {
    frases.push(`É a retomada de um job perdido e só pode rodar em ${job.maquina_prevista_nome ?? "uma máquina específica"}.`);
  }
  if (job.inicio_previsto && job.maquina_prevista_nome) {
    frases.push(
      `${job.maquina_prevista_nome} é a máquina compatível que fica livre primeiro, ${relativo(job.inicio_previsto, agora)} (${horario(job.inicio_previsto, agora)}).`,
    );
  }
  if (job.pool === "interactive") {
    frases.push("Usa a tela: cada máquina roda um job de tela por vez, com Agent ou em modo direto.");
  }
  if (job.motivos.length > 0) {
    frases.push("Os motivos listados acima deixam o horário sem previsão ou incompleto até se resolverem.");
  }
  return (
    <ul className="list-disc space-y-0.5 pl-4">
      {frases.map((f) => (
        <li key={f}>{f}</li>
      ))}
    </ul>
  );
}

function Campo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground lg:hidden">{rotulo}</p>
      <div className="mt-0.5 lg:mt-0">{children}</div>
    </div>
  );
}

function Itens({ itens, className }: { itens: string[]; className?: string }) {
  const visiveis = itens.slice(0, 4);
  const resto = itens.length - visiveis.length;
  return (
    <span className={cn("inline-flex flex-wrap gap-1", className)}>
      {visiveis.map((item) => (
        <span key={item} className="tabular rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">
          {item}
        </span>
      ))}
      {resto > 0 && <span className="text-xs text-muted-foreground">+{resto}</span>}
    </span>
  );
}
