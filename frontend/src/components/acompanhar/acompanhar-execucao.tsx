"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  Lock,
  Maximize2,
  PauseCircle,
  Radio,
  ScrollText,
} from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import {
  MOTIVOS_SEM_PREVISAO,
  PAUSAS,
  SITUACOES,
  nestaTela,
  relogio,
  semImagem,
  type Acompanhamento,
  type LinhaDeLog,
  type Passo,
} from "@/lib/acompanhar";
import { duracao, horario, relativo, rotuloItem } from "@/lib/fila";
import { abrirStream } from "@/lib/stream";
import { cn } from "@/lib/utils";
import { BotaoContinuar, BotaoEncerrar, BotaoParar, LinhaDaSituacao } from "@/components/painel/controle-da-execucao";
import { PageTitle } from "@/components/shared/page-title";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { ImagemDoPasso } from "@/components/acompanhar/imagem-do-passo";

const MAX_LINHAS = 1000;

/** Segundos passados desde `gerado_em`, para os relógios andarem entre um aviso e outro. */
function useRelogio(ativo: boolean): number {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    if (!ativo) return;
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [ativo]);
  return agora;
}

export function AcompanharExecucao({ id }: { id: string }) {
  const { token } = useAuth();
  const caminho = `/execucoes/${id}/acompanhar`;
  const { data, error, refetch } = useApi<Acompanhamento>(caminho, { pollMs: 30000 });
  const [aoVivo, setAoVivo] = useState(false);
  const [logs, setLogs] = useState<LinhaDeLog[]>([]);
  const [mostrarEsperas, setMostrarEsperas] = useState(false);
  const cursor = useRef<string | null>(null);
  const agendado = useRef<ReturnType<typeof setTimeout> | null>(null);
  const podeLogs = data?.pode.ver_telas_e_logs ?? false;

  const buscarLogs = useCallback(
    async (doInicio: boolean) => {
      if (!token || !podeLogs) return;
      const params = new URLSearchParams({ limite: "300", esconder_espera: String(!mostrarEsperas) });
      if (!doInicio && cursor.current) params.set("depois", cursor.current);
      try {
        const pagina = await apiRequest<{ logs: LinhaDeLog[]; cursor: string | null }>(`/execucoes/${id}/logs?${params}`, { token });
        cursor.current = pagina.cursor ?? cursor.current;
        setLogs((anteriores) => (doInicio ? pagina.logs : [...anteriores, ...pagina.logs]).slice(-MAX_LINHAS));
      } catch {
        /* a próxima releitura tenta de novo */
      }
    },
    [id, token, podeLogs, mostrarEsperas],
  );

  useEffect(() => {
    cursor.current = null;
    void buscarLogs(true);
  }, [buscarLogs]);

  useEffect(() => {
    if (!token) return;
    const fechar = abrirStream(
      `/execucoes/${id}/avisos`,
      token,
      (evento) => {
        if (evento.evento !== "mudou" || agendado.current) return;
        agendado.current = setTimeout(() => {
          agendado.current = null;
          void refetch();
          void buscarLogs(false);
        }, 400);
      },
      { aoMudarConexao: setAoVivo },
    );
    return () => {
      fechar();
      if (agendado.current) clearTimeout(agendado.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token, buscarLogs]);

  const agoraMs = useRelogio(Boolean(data?.rodando));

  if (error && !data) return <ErrorState message={error} onRetry={() => void refetch()} />;
  if (!data) return <Carregando />;

  const passou = Math.max(0, Math.floor((agoraMs - new Date(data.gerado_em).getTime()) / 1000));
  const situacao = SITUACOES[data.execucao.status] ?? { texto: data.execucao.status, tom: "neutral" as const };
  const titulo = data.automacao.nome ?? "Execução";

  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Acompanhar"
        title={titulo}
        description={`Execução ${data.execucao.id}${data.automacao.versao ? ` · versão ${data.automacao.versao}` : ""} · pedida ${relativo(data.execucao.criada_em)}`}
        actions={
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground" title={aoVivo ? "Atualiza sozinha" : "Sem conexão ao vivo: relendo a cada 30 s"}>
              <Radio className={cn("h-3.5 w-3.5", aoVivo ? "text-success" : "text-warning")} />
              {aoVivo ? "Ao vivo" : "Reconectando"}
            </span>
            {data.pode.controlar && data.rodando && data.situacao?.tipo === "cancelamento_sem_resposta" && (
              <BotaoEncerrar execucaoId={data.execucao.id} recebido={data.situacao.recebido} grande aoEncerrar={() => void refetch()} />
            )}
            {data.pode.controlar && data.rodando && (
              <BotaoParar execucaoId={data.execucao.id} grande situacao={data.situacao} aoParar={() => void refetch()}
                modo={data.jobs.find((j) => j.status === "running" || j.status === "cancelling")?.modo ?? null} />
            )}
            {data.pode.controlar && !data.rodando && data.execucao.status === "cancelled" && !data.execucao.continuada_em && (
              <BotaoContinuar execucaoId={data.execucao.id} size="md" />
            )}
            <Button variant="outline" size="sm" asChild>
              <Link href={`/executions/${data.execucao.id}`}>Detalhes técnicos</Link>
            </Button>
          </div>
        }
      />

      <Faixa data={data} passou={passou} situacao={situacao} />

      {data.situacao && data.situacao.tipo !== "pausa" && <LinhaDaSituacao situacao={data.situacao} className="py-2.5 text-base" />}
      {(data.execucao.continua_de || data.execucao.continuada_em) && (
        <p className="flex flex-wrap gap-x-4 text-sm text-muted-foreground" data-testid="continuacao">
          {data.execucao.continua_de && (
            <span>Continua a execução <Link href={`/execucoes/${data.execucao.continua_de}`} className="font-medium text-primary hover:underline">que foi cancelada</Link>: só com o que faltava.</span>
          )}
          {data.execucao.continuada_em && (
            <span>Esta execução foi <Link href={`/execucoes/${data.execucao.continuada_em}`} className="font-medium text-primary hover:underline">continuada numa nova</Link>.</span>
          )}
        </p>
      )}
      {data.agora.pausa && (
        <div className="flex items-center gap-2 rounded-lg border border-info/30 bg-info/10 px-4 py-2.5 text-sm">
          <PauseCircle className="h-4 w-4 text-info" />
          <span>
            <strong>{PAUSAS[data.agora.pausa.motivo] ?? "Pausada"}</strong>
            {data.agora.pausa.detalhe ? ` · ${data.agora.pausa.detalhe}` : ""} · desde {horario(data.agora.pausa.desde)}. Esse tempo
            não entra na estimativa.
          </span>
        </div>
      )}
      {data.agora.atencoes.length > 0 && (
        <div className="rounded-lg border border-warning/40 bg-warning/5 px-4 py-3 text-sm">
          <p className="mb-1 flex items-center gap-2 font-semibold text-titulo">
            <AlertTriangle className="h-4 w-4 text-warning" /> Precisa de uma pessoa
          </p>
          <ul className="space-y-0.5">
            {data.agora.atencoes.map((a) => (
              <li key={a.id}>
                {a.item ? <span className="tabular mr-1.5 rounded bg-secondary px-1.5 text-xs">{a.item}</span> : null}
                {a.motivo}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.pode.ver_telas_e_logs ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <TelaAoVivo data={data} passou={passou} />
          <LogAoVivo linhas={logs} mostrarEsperas={mostrarEsperas} alternar={() => setMostrarEsperas((v) => !v)} />
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded-lg border border-dashed border-border bg-muted/40 px-5 py-6 text-sm">
          <Lock className="mt-0.5 h-5 w-5 text-muted-foreground" />
          <div>
            <p className="font-semibold text-titulo">Telas e logs desta automação são restritos</p>
            <p className="text-muted-foreground">
              Você acompanha o andamento, mas as imagens e o log mostram dados de clientes. Peça ao administrador a permissão
              “Ver telas e logs” nesta automação.
            </p>
          </div>
        </div>
      )}

      <Etapas data={data} />
      <Jobs data={data} />
    </div>
  );
}

function Carregando() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Carregando a execução">
      <div className="skeleton h-10 w-72" />
      <div className="skeleton h-28 w-full rounded-xl" />
      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <div className="skeleton h-96" />
        <div className="skeleton h-96" />
      </div>
    </div>
  );
}

function Faixa({ data, passou, situacao }: { data: Acompanhamento; passou: number; situacao: { texto: string; tom: string } }) {
  const p = data.agora.progresso;
  const decorrido = data.decorrido_s != null ? data.decorrido_s + (data.rodando ? passou : 0) : null;
  const falta = data.falta_s != null ? Math.max(data.falta_s - passou, 0) : null;
  const motivo = data.jobs.find((j) => j.status === "running" && j.motivo_sem_previsao)?.motivo_sem_previsao;
  const etapa = data.agora.etapa_atual;
  return (
    <section className="faixa-noite overflow-hidden rounded-xl shadow-md">
      <dl className="grid grid-cols-2 divide-[hsl(var(--faixa-divisao))] md:grid-cols-5 md:divide-x">
        <Numero rotulo="Situação" valor={situacao.texto} detalhe={etapa ? `etapa ${etapa.etapa}${etapa.item ? ` · item ${etapa.item}` : ""}` : data.agora.conclusao?.resumo ?? "—"} pulso={data.rodando} />
        <Numero rotulo="Decorrido" valor={relogio(decorrido)} detalhe={data.execucao.iniciada_em ? `desde ${horario(data.execucao.iniciada_em)}` : "ainda não começou"} />
        <Numero
          rotulo="Falta"
          valor={!data.rodando ? "—" : falta != null ? duracao(falta) : "Sem previsão"}
          detalhe={!data.rodando ? "não está rodando" : falta != null ? "pelas etapas que faltam" : MOTIVOS_SEM_PREVISAO[motivo ?? ""] ?? "sem base de histórico"}
          alerta={data.rodando && falta == null}
        />
        <Numero
          rotulo="Término previsto"
          valor={data.execucao.concluida_em ? horario(data.execucao.concluida_em) : data.termino_previsto ? horario(data.termino_previsto) : "—"}
          detalhe={data.execucao.concluida_em ? "terminou" : data.termino_previsto ? relativo(data.termino_previsto) : "sem previsão"}
        />
        <div className="col-span-2 px-5 py-4 md:col-span-1">
          <dt className="text-xs font-bold uppercase tracking-[0.16em] faixa-rotulo">Progresso</dt>
          <dd className="titulo-condensado mt-1 text-3xl leading-none">{p ? `${p.atual}/${p.total}` : "—"}</dd>
          <dd className="mt-2 h-1.5 overflow-hidden rounded-full bg-[hsl(var(--faixa-divisao))]">
            <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: p ? `${Math.round((p.atual / Math.max(p.total, 1)) * 100)}%` : "0%" }} />
          </dd>
          <dd className="mt-1.5 truncate text-xs faixa-apoio">{p?.rotulo ?? "a automação não informou progresso"}</dd>
        </div>
      </dl>
    </section>
  );
}

function Numero({ rotulo, valor, detalhe, alerta, pulso }: { rotulo: string; valor: string; detalhe: string; alerta?: boolean; pulso?: boolean }) {
  return (
    <div className="px-5 py-4">
      <dt className="text-xs font-bold uppercase tracking-[0.16em] faixa-rotulo">{rotulo}</dt>
      <dd className={cn("titulo-condensado mt-1 flex items-center gap-2 text-3xl leading-none", alerta ? "faixa-alerta" : "faixa-valor")}>
        {pulso && <span className="h-2 w-2 animate-pulse-dot rounded-full bg-success" />}
        {valor}
      </dd>
      <dd className="mt-1.5 truncate text-xs faixa-apoio">{detalhe}</dd>
    </div>
  );
}

function TelaAoVivo({ data, passou }: { data: Acompanhamento; passou: number }) {
  const passos = data.agora.passos;
  const comImagem = useMemo(() => passos.filter((p) => p.imagem_id), [passos]);
  const [fixado, setFixado] = useState<string | null>(null);
  const [ampliada, setAmpliada] = useState(false);
  const trilha = useRef<HTMLDivElement>(null);
  const tela = data.agora.tela;
  const escolhido: Passo | null = fixado ? passos.find((p) => p.id === fixado) ?? null : null;
  const imagemId = escolhido ? escolhido.imagem_id : tela?.imagem_id ?? null;
  const recusa = semImagem(escolhido ? escolhido.imagem : tela?.imagem);
  const segundos = !escolhido && tela?.segundos_nesta_tela != null ? tela.segundos_nesta_tela + passou : null;
  const indice = escolhido ? comImagem.findIndex((p) => p.id === escolhido.id) : comImagem.length - 1;

  function irPara(delta: number) {
    const alvo = comImagem[Math.min(Math.max(indice + delta, 0), comImagem.length - 1)];
    if (!alvo) return;
    setFixado(alvo === comImagem[comImagem.length - 1] ? null : alvo.id);
  }

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="eyebrow text-xs">{escolhido ? "Passo anterior" : data.rodando ? "Tela agora" : "Última tela"}</p>
          <p className="truncate font-semibold text-titulo">{(escolhido ?? tela)?.rotulo ?? "Sem passos com imagem ainda"}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {escolhido && (
            <Button size="sm" variant="primary" onClick={() => setFixado(null)}>
              <Radio className="h-3.5 w-3.5" /> Voltar ao vivo
            </Button>
          )}
          <Button size="icon" variant="ghost" onClick={() => irPara(-1)} disabled={indice <= 0} aria-label="Passo anterior">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => irPara(1)} disabled={indice >= comImagem.length - 1} aria-label="Próximo passo">
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => setAmpliada(true)} disabled={!imagemId || Boolean(recusa)} aria-label="Ampliar a tela">
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>
      </header>
      <div className="relative bg-[hsl(var(--tela-fundo))]">
        <ImagemDoPasso execucao={data.execucao.id} imagem={imagemId} tamanho="media" alt={(escolhido ?? tela)?.rotulo ?? "Tela"} recusada={recusa} className="aspect-video w-full" />
        {segundos != null && (
          <span className="titulo-condensado absolute bottom-3 left-3 rounded-md bg-[#0e1729]/85 px-2.5 py-1 text-base text-white ring-1 ring-nevoa/40">
            {nestaTela(segundos)}
            {tela?.espera_rotulo ? <span className="ml-1.5 font-sans text-xs text-nevoa">· {tela.espera_rotulo}</span> : null}
          </span>
        )}
        {(escolhido ?? tela)?.item && (
          <span className="tabular absolute right-3 top-3 rounded bg-[#0e1729]/85 px-2 py-0.5 text-xs text-white">item {(escolhido ?? tela)?.item}</span>
        )}
      </div>
      {comImagem.length > 0 && (
        <div ref={trilha} className="flex gap-2 overflow-x-auto border-t border-border p-3" aria-label="Passos com imagem">
          {comImagem.map((p, i) => {
            const ativo = escolhido ? p.id === escolhido.id : i === comImagem.length - 1;
            return (
              <button
                key={p.id}
                onClick={() => setFixado(i === comImagem.length - 1 ? null : p.id)}
                className={cn("w-28 shrink-0 overflow-hidden rounded-md border text-left", ativo ? "border-primary ring-2 ring-primary/40" : "border-border")}
                title={`${p.rotulo ?? ""} · ${horario(p.quando)}`}
              >
                <ImagemDoPasso execucao={data.execucao.id} imagem={p.imagem_id} tamanho="miniatura" alt={p.rotulo ?? "Passo"} recusada={semImagem(p.imagem)} className="aspect-video w-full" />
                <span className={cn("block truncate px-1.5 py-1 text-xs", p.tipo === "falha" ? "text-destructive" : "text-muted-foreground")}>{p.rotulo}</span>
              </button>
            );
          })}
        </div>
      )}
      <Modal open={ampliada} onClose={() => setAmpliada(false)} title={(escolhido ?? tela)?.rotulo ?? "Tela"} className="max-w-6xl">
        {ampliada && imagemId ? <ImagemDoPasso execucao={data.execucao.id} imagem={imagemId} tamanho="cheia" alt="Tela ampliada" className="w-full" /> : null}
      </Modal>
    </section>
  );
}

const CORES_NIVEL: Record<string, string> = {
  debug: "text-muted-foreground",
  info: "text-foreground",
  aviso: "text-warning",
  erro: "text-destructive",
  critico: "text-destructive font-semibold",
};

function LogAoVivo({ linhas, mostrarEsperas, alternar }: { linhas: LinhaDeLog[]; mostrarEsperas: boolean; alternar: () => void }) {
  const caixa = useRef<HTMLDivElement>(null);
  const colado = useRef(true);
  useEffect(() => {
    const el = caixa.current;
    if (el && colado.current) el.scrollTop = el.scrollHeight;
  }, [linhas]);
  return (
    <section className="flex min-h-[24rem] flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm xl:max-h-[38rem]">
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <p className="flex items-center gap-2 font-semibold text-titulo">
          <ScrollText className="h-4 w-4 text-muted-foreground" /> Log ao vivo
        </p>
        <Button size="sm" variant="ghost" onClick={alternar} aria-pressed={mostrarEsperas}>
          {mostrarEsperas ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          {mostrarEsperas ? "Ocultar esperas" : "Mostrar esperas"}
        </Button>
      </header>
      <div
        ref={caixa}
        onScroll={(e) => {
          const el = e.currentTarget;
          colado.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
        className="flex-1 overflow-y-auto bg-muted/40 px-3 py-2 font-mono text-xs leading-relaxed"
        data-testid="log-ao-vivo"
      >
        {linhas.length === 0 ? (
          <p className="py-8 text-center font-sans text-sm text-muted-foreground">Nenhuma linha de log ainda.</p>
        ) : (
          linhas.map((l) => (
            <p key={l.id} className={cn("whitespace-pre-wrap break-words", CORES_NIVEL[l.nivel ?? "info"], l.espera && "opacity-60")}>
              <span className="mr-2 text-muted-foreground">{new Date(l.quando).toLocaleTimeString("pt-BR")}</span>
              {l.item ? <span className="mr-1.5 text-muted-foreground">[{l.item}]</span> : null}
              {l.texto}
            </p>
          ))
        )}
      </div>
    </section>
  );
}

const SITUACAO_ETAPA: Record<string, { texto: string; tom: "success" | "warning" | "destructive" | "info" | "neutral" }> = {
  pendente: { texto: "A fazer", tom: "neutral" },
  executando: { texto: "Fazendo", tom: "info" },
  ok: { texto: "Feita", tom: "success" },
  erro: { texto: "Erro", tom: "destructive" },
  interrompida: { texto: "Interrompida", tom: "warning" },
};

function Etapas({ data }: { data: Acompanhamento }) {
  const linhas = data.estimativa.jobs.flatMap((j) => j.etapas);
  if (linhas.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="titulo-condensado text-xl">Etapas: estimativa e tempo real</h2>
      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
            <tr>
              <th className="px-4 py-2.5">Etapa</th>
              <th className="px-4 py-2.5">Item</th>
              <th className="px-4 py-2.5">Situação</th>
              <th className="px-4 py-2.5">Estimativa</th>
              <th className="px-4 py-2.5">Real</th>
              <th className="px-4 py-2.5">Base</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {linhas.map((e) => {
              const s = SITUACAO_ETAPA[e.situacao] ?? { texto: e.situacao, tom: "neutral" as const };
              return (
                <tr key={`${e.etapa}-${e.item ?? ""}`}>
                  <td className="px-4 py-2.5 font-medium text-titulo">{e.nome}</td>
                  <td className="tabular px-4 py-2.5 text-xs">{e.item ?? "—"}</td>
                  <td className="px-4 py-2.5"><Badge tone={s.tom}>{s.texto}</Badge></td>
                  <td className="px-4 py-2.5">
                    {e.estimativa_s != null ? <span className="titulo-condensado text-base">{duracao(e.estimativa_s)}</span> : <span className="font-medium text-warning">Sem previsão</span>}
                    {e.tarefas_previstas != null && <span className="ml-1.5 text-xs text-muted-foreground">{e.tarefas_feitas}/{e.tarefas_previstas}</span>}
                  </td>
                  <td className="px-4 py-2.5">{e.real_s != null ? duracao(e.real_s) : "—"}</td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground first-letter:uppercase">{e.base?.texto ?? e.motivo_texto ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Jobs({ data }: { data: Acompanhamento }) {
  return (
    <section className="space-y-3">
      <h2 className="titulo-condensado text-xl">Onde roda</h2>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.jobs.map((j) => {
          const s = SITUACOES[j.status] ?? { texto: j.status, tom: "neutral" as const };
          return (
            <article key={j.job_id} className="rounded-lg border border-border bg-card p-4 text-sm shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-titulo">{j.maquina_nome ?? "Máquina ainda não definida"}</p>
                  <p className="text-xs text-muted-foreground">
                    {j.modo === "direct" ? "Modo direto" : j.modo ? "Agent" : "—"}
                    {j.tentativa ? ` · tentativa ${j.tentativa}` : ""}
                  </p>
                </div>
                <Badge tone={s.tom}>{s.texto}</Badge>
              </div>
              <p className="mt-2 flex flex-wrap gap-1">
                {j.itens.slice(0, 6).map((i) => (
                  <span key={rotuloItem(i)} className="tabular rounded bg-secondary px-1.5 py-0.5 text-xs">{rotuloItem(i)}</span>
                ))}
              </p>
              {j.status === "running" && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {j.falta_s != null ? `falta ${duracao(j.falta_s)}` : `sem previsão: ${MOTIVOS_SEM_PREVISAO[j.motivo_sem_previsao ?? ""] ?? "sem base"}`}
                </p>
              )}
              {j.falha && <p className="mt-2 text-xs text-destructive">{j.falha}</p>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
