"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { AlertTriangle, Clock3, LayoutGrid, MonitorPlay, Radio } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAvisos, useSegundosDesde } from "@/hooks/use-avisos";
import { MOTIVOS_SEM_PREVISAO, nestaTela, relogio, semImagem } from "@/lib/acompanhar";
import { duracao, horario, relativo } from "@/lib/fila";
import type { ExecucaoAoVivo, JobEsperando, MaquinaNoPainel, Painel } from "@/lib/painel";
import { cn } from "@/lib/utils";
import { ErrorState } from "@/components/shared/error-state";
import { ImagemDoPasso } from "@/components/acompanhar/imagem-do-passo";
import { BotaoExecutar, UltimasAutomacoes, useDisparo } from "@/components/painel/disparo-rapido";
import { BotaoEncerrar, BotaoParar, LinhaDaSituacao } from "@/components/painel/controle-da-execucao";

const GRADES = [1, 2, 4, 6, 9] as const;
const COLUNAS: Record<number, string> = { 1: "grid-cols-1", 2: "lg:grid-cols-2", 4: "lg:grid-cols-2", 6: "lg:grid-cols-3", 9: "lg:grid-cols-3" };
const CHAVE_MODO = "portal.painel.modo";
const CHAVE_GRADE = "portal.painel.grade";
const CHAVE_MAQUINA = "portal.painel.maquina";

function lembrar(chave: string, valor: string) {
  try {
    window.localStorage.setItem(chave, valor);
  } catch {
    /* sem armazenamento: só não lembra */
  }
}

export function PainelAoVivo() {
  const { data, error, refetch } = useApi<Painel>("/painel", { pollMs: 30000 });
  const aoVivo = useAvisos("/painel/avisos", () => void refetch(), 800);
  const passou = useSegundosDesde(data?.gerado_em, Boolean(data?.execucoes.length));
  const [modo, setModo] = useState<"monitores" | "central">("monitores");
  const [grade, setGrade] = useState<number>(4);
  const [pedidos, setPedidos] = useState(0);
  const [maquina, setMaquina] = useState("");
  const { disparar, janela } = useDisparo(() => { setPedidos((n) => n + 1); void refetch(); });

  useEffect(() => {
    try {
      setMaquina(window.localStorage.getItem(CHAVE_MAQUINA) ?? "");
      if (window.localStorage.getItem(CHAVE_MODO) === "central") setModo("central");
      const g = Number(window.localStorage.getItem(CHAVE_GRADE));
      if (GRADES.includes(g as (typeof GRADES)[number])) setGrade(g);
    } catch {
      /* ignora */
    }
  }, []);

  if (error && !data) return <ErrorState message={error} onRetry={() => void refetch()} />;
  if (!data) return <div className="skeleton h-[60vh] w-full rounded-xl" aria-busy="true" aria-label="Carregando o painel" />;

  const central = data.central && modo === "central";
  // A máquina escolhida some da lista (removida ou sem permissão): volta para "Todas".
  const filtro = data.maquinas.some((m) => m.id === maquina) ? maquina : "";
  const daMaquina = (id: string | null | undefined) => !filtro || id === filtro;
  const execucoes = data.execucoes.filter((e) => daMaquina(e.maquina_id));
  const rodando = execucoes.filter((e) => !e.situacao);
  const paradas = execucoes.filter((e) => e.situacao);
  const fila = (data.aguardando?.fila ?? []).filter((j) => daMaquina(j.maquina_id));
  const perdidos = (data.aguardando?.perdidos ?? []).filter((j) => daMaquina(j.maquina_id));
  const nada = rodando.length + paradas.length + fila.length + perdidos.length === 0;
  function escolher(id: string) {
    setMaquina(id);
    lembrar(CHAVE_MAQUINA, id);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Monitorar</p>
          <h1 className="titulo-condensado text-4xl">Agora</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground" title={aoVivo ? "Atualiza sozinho" : "Sem conexão ao vivo: relendo a cada 30 s"}>
            <Radio className={cn("h-4 w-4", aoVivo ? "text-success" : "text-warning")} />
            {aoVivo ? "Ao vivo" : "Reconectando"}
          </span>
          {data.central && (
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex rounded-lg border border-border bg-card p-1" role="tablist" aria-label="Modo do painel">
                {(["monitores", "central"] as const).map((m) => (
                  <button
                    key={m}
                    role="tab"
                    aria-selected={modo === m}
                    onClick={() => {
                      setModo(m);
                      lembrar(CHAVE_MODO, m);
                    }}
                    className={cn("flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium",
                      modo === m ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}
                  >
                    {m === "monitores" ? <MonitorPlay className="h-4 w-4" /> : <LayoutGrid className="h-4 w-4" />}
                    {m === "monitores" ? "Monitores" : "Central de telas"}
                  </button>
                ))}
              </div>
              {central && (
                <div className="flex rounded-lg border border-border bg-card p-1" aria-label="Telas por vez">
                  {GRADES.map((g) => (
                    <button
                      key={g}
                      onClick={() => {
                        setGrade(g);
                        lembrar(CHAVE_GRADE, String(g));
                      }}
                      aria-pressed={grade === g}
                      className={cn("min-w-9 rounded-md px-2 py-1.5 text-sm font-semibold tabular",
                        grade === g ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <BotaoExecutar disparar={disparar} />
        </div>
      </div>

      {!central && data.maquinas.length > 0 && (
        <AbasDeMaquina maquinas={data.maquinas} execucoes={data.execucoes} escolhida={filtro} escolher={escolher} />
      )}

      {central ? (
        <Central data={data} grade={grade} passou={passou} />
      ) : (
        <>
          {nada && <NadaRodando maquinas={data.maquinas.filter((m) => daMaquina(m.id))} filtrada={Boolean(filtro)} />}
          {rodando.length > 0 && (
            <Secao titulo="Rodando agora" total={rodando.length} id="rodando">
              <div className="grid gap-6 xl:grid-cols-2 min-[1800px]:grid-cols-3">
                {rodando.map((e) => <Monitor key={e.execucao_id} e={e} passou={passou} aoMudar={() => void refetch()} />)}
              </div>
            </Secao>
          )}
          {paradas.length > 0 && (
            <Secao titulo="Pausadas ou esperando" total={paradas.length} id="paradas"
              explica="Rodando, mas paradas em alguma coisa: uma pausa, uma espera, a comunicação ou um pedido de parada.">
              <div className="grid gap-6 xl:grid-cols-2 min-[1800px]:grid-cols-3">
                {paradas.map((e) => <Monitor key={e.execucao_id} e={e} passou={passou} aoMudar={() => void refetch()} />)}
              </div>
            </Secao>
          )}
          {fila.length + perdidos.length > 0 && (
            <Secao titulo="Esperando para começar" total={fila.length + perdidos.length} id="esperando"
              acao={<Link href="/fila" className="text-sm font-medium text-primary hover:underline">Abrir a Fila</Link>}>
              <Esperando fila={fila} perdidos={perdidos} />
            </Secao>
          )}
          <UltimasAutomacoes disparar={disparar} atualizar={pedidos} maquina={filtro} />
        </>
      )}

      {janela}
    </div>
  );
}

function Secao({ titulo, total, id, explica, acao, children }: {
  titulo: string; total: number; id: string; explica?: string; acao?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="space-y-3" data-testid={`secao-${id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="flex items-baseline gap-3 titulo-condensado text-2xl">
          {titulo} <span className="font-sans text-base font-normal text-muted-foreground">{total}</span>
        </h2>
        {acao}
      </div>
      {explica && <p className="-mt-1 text-sm text-muted-foreground">{explica}</p>}
      {children}
    </section>
  );
}

function estadoDaMaquina(m: MaquinaNoPainel): { texto: string; cor: string } {
  if (!m.online) return { texto: "sem sinal", cor: "bg-destructive" };
  if (m.job_perdido) return { texto: "job perdido", cor: "bg-warning" };
  if (m.sessao_bloqueada) return { texto: "sessão bloqueada", cor: "bg-warning" };
  if (m.ocupada) return { texto: "rodando", cor: "bg-info" };
  return { texto: "livre", cor: "bg-success" };
}

/** As máquinas viram o filtro do Painel: tudo abaixo mostra só o que é da máquina escolhida. */
function AbasDeMaquina({ maquinas, execucoes, escolhida, escolher }: {
  maquinas: MaquinaNoPainel[]; execucoes: ExecucaoAoVivo[]; escolhida: string; escolher: (id: string) => void;
}) {
  const aba = (ativa: boolean) => cn("flex shrink-0 items-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors",
    ativa ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground");
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex max-w-full gap-1 overflow-x-auto rounded-lg border border-border bg-card p-1" role="tablist" aria-label="Máquina">
        <button role="tab" aria-selected={!escolhida} onClick={() => escolher("")} className={aba(!escolhida)}>
          Todas
        </button>
        {maquinas.map((m) => {
          const { texto, cor } = estadoDaMaquina(m);
          const ativa = escolhida === m.id;
          return (
            <button key={m.id} role="tab" aria-selected={ativa} onClick={() => escolher(m.id)} className={aba(ativa)}
              data-maquina={m.id} title={`${m.nome ?? m.id}: ${texto}`}>
              <span className={cn("h-2.5 w-2.5 rounded-full", cor)} />
              {m.nome ?? m.id}
              <span className={cn("font-normal", ativa ? "opacity-80" : "text-muted-foreground")}>{texto}</span>
            </button>
          );
        })}
      </div>
      <Link href="/maquinas" className="text-sm font-medium text-primary hover:underline">Linha do tempo das máquinas</Link>
    </div>
  );
}

/** Na fila esperando máquina e perdidos esperando decisão, uma linha cada. */
function Esperando({ fila, perdidos }: { fila: JobEsperando[]; perdidos: JobEsperando[] }) {
  const itens = (j: JobEsperando) => (j.itens.length === 0 ? "" : j.itens.length <= 3 ? j.itens.join(", ") : `${j.itens.length} itens`);
  return (
    <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="esperando">
      {perdidos.map((j) => (
        <li key={j.job_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5" data-job={j.job_id}>
          <AlertTriangle className="h-5 w-5 shrink-0 text-warning" />
          <Link href={`/execucoes/${j.execucao_id}`} className="min-w-0 flex-1 hover:underline">
            <span className="font-semibold text-titulo">{j.automacao ?? "Automação"}</span>
            {itens(j) && <span className="text-muted-foreground"> · {itens(j)}</span>}
          </Link>
          <span className="text-sm text-warning">
            Perdida{j.maquina ? ` em ${j.maquina}` : ""}{j.perdido_em ? ` ${relativo(j.perdido_em)}` : ""}: esperando uma decisão
          </span>
          <Link href="/fila" className="text-sm font-medium text-primary hover:underline">Decidir</Link>
        </li>
      ))}
      {fila.map((j) => (
        <li key={j.job_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5" data-job={j.job_id}>
          <Clock3 className="h-5 w-5 shrink-0 text-muted-foreground" />
          <Link href={`/execucoes/${j.execucao_id}`} className="min-w-0 flex-1 hover:underline">
            <span className="font-semibold text-titulo">{j.automacao ?? "Automação"}</span>
            {itens(j) && <span className="text-muted-foreground"> · {itens(j)}</span>}
          </Link>
          <span className="text-sm text-muted-foreground" title={(j.motivos ?? []).join("; ")}>
            {j.inicio_previsto ? `Começa às ${horario(j.inicio_previsto)}${j.maquina ? ` em ${j.maquina}` : ""}`
              : (j.motivos ?? [])[0] ?? "Na fila, sem previsão"}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Tempos({ e, passou, grande = true }: { e: ExecucaoAoVivo; passou: number; grande?: boolean }) {
  const falta = e.falta_s != null ? Math.max(e.falta_s - passou, 0) : null;
  const valor = grande ? "titulo-condensado text-3xl leading-none" : "titulo-condensado text-xl leading-none";
  return (
    <dl className="grid grid-cols-3 gap-4">
      <div>
        <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Falta</dt>
        <dd className={cn(valor, falta == null && "text-warning")}>{falta != null ? duracao(falta) : "Sem previsão"}</dd>
        {falta == null && <dd className="mt-1 text-xs text-muted-foreground">{MOTIVOS_SEM_PREVISAO[e.motivo_sem_previsao ?? ""] ?? "sem base de histórico"}</dd>}
      </div>
      <div>
        <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Termina</dt>
        <dd className={valor}>{e.termino_previsto ? horario(e.termino_previsto) : "—"}</dd>
      </div>
      <div>
        <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Rodando há</dt>
        <dd className={valor}>{relogio(e.decorrido_s != null ? e.decorrido_s + passou : null)}</dd>
      </div>
    </dl>
  );
}

function Progresso({ e }: { e: ExecucaoAoVivo }) {
  const p = e.progresso;
  const pct = p ? Math.round((p.atual / Math.max(p.total, 1)) * 100) : null;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
        <span className="truncate font-medium text-titulo">
          {e.etapa ? nomeDaEtapa(e.etapa.etapa) : "Começando"}
          {e.item ? <span className="font-normal text-muted-foreground"> · {e.item.rotulo ?? e.item.item}</span> : null}
        </span>
        <span className="tabular shrink-0 text-muted-foreground">{p ? `${p.atual}/${p.total}` : ""}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-secondary">
        <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: pct != null ? `${pct}%` : "0%" }} />
      </div>
    </div>
  );
}

function nomeDaEtapa(chave: string): string {
  const texto = chave.replace(/[_-]+/g, " ").trim();
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function Monitor({ e, passou, aoMudar }: { e: ExecucaoAoVivo; passou: number; aoMudar?: () => void }) {
  const segundos = e.tela?.segundos_nesta_tela != null ? e.tela.segundos_nesta_tela + passou : null;
  return (
    <article
      className="group relative overflow-hidden rounded-xl border border-border bg-card shadow-sm transition-shadow hover:shadow-md"
      data-testid="monitor"
    >
      <Link href={`/execucoes/${e.execucao_id}`} className="absolute inset-0 z-0" aria-label={`Acompanhar ${e.automacao ?? "a execução"}`} />
      <div className="pointer-events-none relative">
      {e.pode_ver_tela && (
        <div className="relative bg-[hsl(var(--tela-fundo))]">
          <ImagemDoPasso
            execucao={e.execucao_id}
            imagem={e.tela?.imagem_id ?? null}
            tamanho="media"
            alt={e.tela?.rotulo ?? "Tela"}
            recusada={semImagem(e.tela?.imagem)}
            className="aspect-video w-full"
          />
          {segundos != null && (
            <span className="titulo-condensado absolute bottom-3 left-3 rounded-md bg-[#0e1729]/85 px-3 py-1 text-lg text-white ring-1 ring-nevoa/40">
              {nestaTela(segundos)}
            </span>
          )}
        </div>
      )}
      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-xl font-semibold text-titulo group-hover:underline">{e.automacao ?? "Automação"}</p>
            <p className="text-sm text-muted-foreground">
              {e.maquina ?? "Máquina"} {e.itens.length > 0 && `· ${e.itens.length === 1 ? e.itens[0].chave : `${e.itens.length} itens`}`}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {e.atencoes > 0 && (
              <span className="flex items-center gap-1.5 rounded-md bg-warning/15 px-2.5 py-1 text-sm font-medium text-warning"
                title="Itens que precisam de uma pessoa">
                <AlertTriangle className="h-4 w-4" /> {e.atencoes}
              </span>
            )}
            {e.pode_controlar && (
              <span className="pointer-events-auto relative z-10">
                {e.situacao?.tipo === "cancelamento_sem_resposta" ? (
                  <BotaoEncerrar execucaoId={e.execucao_id} recebido={e.situacao.recebido} aoEncerrar={aoMudar} />
                ) : (
                  <BotaoParar execucaoId={e.execucao_id} modo={e.modo} situacao={e.situacao} aoParar={aoMudar} />
                )}
              </span>
            )}
          </div>
        </div>
        <LinhaDaSituacao situacao={e.situacao} />
        <Progresso e={e} />
        <Tempos e={e} passou={passou} />
        {e.log && e.log.length > 0 && (
          <div className="space-y-0.5 rounded-lg bg-muted px-3 py-2 font-mono text-sm text-muted-foreground">
            {e.log.slice(-3).map((l) => (
              <p key={l.id} className={cn("truncate", l.nivel === "erro" && "text-destructive", l.nivel === "aviso" && "text-warning")}>
                {l.texto}
              </p>
            ))}
          </div>
        )}
      </div>
      </div>
    </article>
  );
}

function Central({ data, grade, passou }: { data: Painel; grade: number; passou: number }) {
  const porMaquina = new Map(data.execucoes.filter((e) => e.maquina_id).map((e) => [e.maquina_id as string, e]));
  const ordenadas = [...data.maquinas].sort((a, b) => Number(porMaquina.has(b.id)) - Number(porMaquina.has(a.id)));
  const visiveis = ordenadas.slice(0, grade);
  return (
    <div className={cn("grid gap-4", COLUNAS[grade])} data-testid="central">
      {visiveis.map((m) => {
        const e = porMaquina.get(m.id);
        return e ? <QuadroAoVivo key={m.id} e={e} passou={passou} compacto={grade >= 6} /> : <QuadroLivre key={m.id} m={m} />;
      })}
      {visiveis.length === 0 && <p className="text-muted-foreground">Nenhuma máquina cadastrada.</p>}
    </div>
  );
}

function QuadroAoVivo({ e, passou, compacto }: { e: ExecucaoAoVivo; passou: number; compacto: boolean }) {
  const segundos = e.tela?.segundos_nesta_tela != null ? e.tela.segundos_nesta_tela + passou : null;
  return (
    <article className="overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="quadro">
      <Link href={`/execucoes/${e.execucao_id}`} className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5 hover:bg-muted">
        <span className="truncate font-semibold text-titulo">
          {e.maquina} <span className="font-normal text-muted-foreground">· {e.automacao}</span>
        </span>
        <span className="h-2.5 w-2.5 shrink-0 animate-pulse-dot rounded-full bg-success" />
      </Link>
      <div className={cn("grid", !compacto && "md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]")}>
        <div className="relative bg-[hsl(var(--tela-fundo))]">
          <ImagemDoPasso execucao={e.execucao_id} imagem={e.tela?.imagem_id ?? null} tamanho="media" alt={e.tela?.rotulo ?? "Tela"}
            recusada={semImagem(e.tela?.imagem)} className="aspect-video w-full" />
          {segundos != null && (
            <span className="titulo-condensado absolute bottom-2 left-2 rounded bg-[#0e1729]/85 px-2 py-0.5 text-white">{nestaTela(segundos)}</span>
          )}
        </div>
        {!compacto && (
          <div className="flex max-h-72 flex-col gap-0.5 overflow-hidden border-t border-border bg-muted/50 px-3 py-2 font-mono text-sm md:border-l md:border-t-0">
            {(e.log ?? []).map((l) => (
              <p key={l.id} className={cn("line-clamp-2 break-words text-muted-foreground", l.nivel === "erro" && "text-destructive", l.nivel === "aviso" && "text-warning")}>
                {l.texto}
              </p>
            ))}
            {(e.log ?? []).length === 0 && <p className="font-sans text-muted-foreground">Sem log ainda.</p>}
          </div>
        )}
      </div>
      <div className="space-y-3 px-4 py-3">
        <LinhaDaSituacao situacao={e.situacao} />
        <Progresso e={e} />
        {!compacto && <Tempos e={e} passou={passou} grande={false} />}
      </div>
    </article>
  );
}

function QuadroLivre({ m }: { m: MaquinaNoPainel }) {
  const situacao = !m.online ? "Sem sinal" : m.job_perdido ? "Job perdido" : m.sessao_bloqueada ? "Sessão bloqueada" : m.ocupada ? "Ocupada" : "Livre";
  return (
    <article className="flex min-h-48 flex-col justify-between rounded-xl border border-dashed border-border bg-card/60 p-5" data-testid="quadro">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-titulo">{m.nome ?? m.id}</p>
        <span className={cn("text-sm font-medium", situacao === "Livre" ? "text-success" : "text-warning")}>{situacao}</span>
      </div>
      <p className="text-sm text-muted-foreground">
        {m.proximo ? `Próximo: ${m.proximo.automacao ?? "um job"}${m.proximo.inicio_previsto ? ` às ${horario(m.proximo.inicio_previsto)}` : ""}` : "Nada na fila para esta máquina."}
      </p>
    </article>
  );
}

function NadaRodando({ maquinas, filtrada }: { maquinas: MaquinaNoPainel[]; filtrada: boolean }) {
  const proximo = maquinas.map((m) => m.proximo).find((p) => p?.inicio_previsto);
  return (
    <div className="flex items-center gap-4 rounded-xl border border-dashed border-border bg-card/60 px-6 py-5" data-testid="nada-rodando">
      <MonitorPlay className="h-8 w-8 shrink-0 text-muted-foreground" />
      <div>
        <p className="titulo-condensado text-xl">{filtrada ? "Nada rodando nesta máquina" : "Nada rodando agora"}</p>
        <p className="text-muted-foreground">
          {proximo ? `O próximo job começa ${relativo(proximo.inicio_previsto)}, às ${horario(proximo.inicio_previsto)}.`
            : filtrada ? "Nada na fila para esta máquina." : "A fila está vazia."}
        </p>
      </div>
    </div>
  );
}
