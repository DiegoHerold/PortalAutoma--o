"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Pencil, Play, Plus, Repeat, X } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { FUSO_PADRAO, descrever, horaTexto, mover, noFuso, type Movimento } from "@/lib/agenda";
import { addDays, addMonths, getMonthGridDays, getWeekDays, isSameDay, monthLabel, parseDateKey, toDateKey } from "@/lib/calendar";
import { hasPermission } from "@/lib/permissions";
import { triggerSchedule, updateSchedule } from "@/lib/schedule-api";
import { temporalStatusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";
import { SEMANA, corDe, duracaoMin, nomeDe, podeArrastar, pontoDe, type Alvo, type Arraste, type Comum } from "@/components/schedules/agenda/agenda-comum";
import { GradeDeHoras } from "@/components/schedules/agenda/grade-de-horas";
import { ScheduleDetailSheet } from "@/components/schedules/schedule-detail-sheet";
import { ScheduleFormSheet, type PrefillDoAgendamento } from "@/components/schedules/schedule-form-sheet";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import type { Automation } from "@/types/automation";
import type { Flow } from "@/types/flow";
import type { Schedule, ScheduleCalendarItem, ScheduleCalendarResponse } from "@/types/schedule";

type Visao = "dia" | "semana" | "mes";
const VISOES: Array<{ id: Visao; rotulo: string }> = [{ id: "dia", rotulo: "Dia" }, { id: "semana", rotulo: "Semana" }, { id: "mes", rotulo: "Mês" }];
const HORA_REM = 3.25;  // altura de uma hora na grade
const ROTULO_MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/**
 * Agendamentos como uma agenda (pedido de 12/11/2026, no estilo da agenda do Google): só o
 * calendário. Clique num horário vazio cria; arraste uma ocorrência futura para mudar o dia ou a
 * hora; clique numa ocorrência para ver, editar ou executar agora.
 */
export function AgendaCalendario() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { token, user } = useAuth();
  const { toast } = useToast();
  const podeEscrever = hasPermission(user, "schedule.update");
  const podeExecutar = hasPermission(user, "schedule.trigger") || podeEscrever;

  const visao: Visao = (["dia", "semana", "mes"] as const).find((v) => v === params.get("visao")) ?? "semana";
  const ancora = params.get("data") ? parseDateKey(params.get("data")!) : new Date();
  const dias = useMemo(() => {
    if (visao === "dia") return [new Date(ancora.getFullYear(), ancora.getMonth(), ancora.getDate())];
    if (visao === "semana") return getWeekDays(ancora);
    return getMonthGridDays(ancora).map((d) => d.date);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visao, toDateKey(ancora)]);
  const de = toDateKey(dias[0]);
  const ate = toDateKey(dias[dias.length - 1]);
  const calendario = useApi<ScheduleCalendarResponse>(
    `/schedules/calendar?from=${de}&to=${ate}&timezone=${encodeURIComponent(FUSO_PADRAO)}&view=${visao === "mes" ? "month" : visao === "dia" ? "day" : "week"}&target_type=all`,
    { pollMs: 60000 });
  const automacoes = useApi<Automation[]>("/automations");
  const fluxos = useApi<Flow[]>("/flows");

  const [aberto, setAberto] = useState<{ item: ScheduleCalendarItem; x: number; y: number } | null>(null);
  const [form, setForm] = useState<{ editando: number | null; prefill?: PrefillDoAgendamento } | null>(null);
  const [detalhe, setDetalhe] = useState<ScheduleCalendarItem | null>(null);
  const [arraste, setArraste] = useState<Arraste | null>(null);
  const [alvo, setAlvo] = useState<Alvo | null>(null);
  const [confirmar, setConfirmar] = useState<{ id: number; mov: Extract<Movimento, { ok: true }> } | null>(null);

  const porDia = useMemo(() => {
    const mapa = new Map<string, Array<{ item: ScheduleCalendarItem; inicio: number; fim: number }>>();
    for (const item of calendario.data?.items ?? []) {
      const { dia, minutos } = noFuso(item.actual_start ?? item.planned_start, item.timezone || FUSO_PADRAO);
      const lista = mapa.get(dia) ?? [];
      lista.push({ item, inicio: minutos, fim: Math.min(minutos + duracaoMin(item), 1440) });
      mapa.set(dia, lista);
    }
    return mapa;
  }, [calendario.data]);

  // Lê o endereço na hora do clique: dois cliques rápidos andam duas casas, não repetem a mesma.
  function atual(): { p: URLSearchParams; ancora: Date; visao: Visao } {
    const p = new URLSearchParams(window.location.search);
    const v = (["dia", "semana", "mes"] as const).find((x) => x === p.get("visao")) ?? "semana";
    return { p, ancora: p.get("data") ? parseDateKey(p.get("data")!) : new Date(), visao: v };
  }

  function irPara(nova: { visao?: Visao; data?: Date }) {
    const { p } = atual();
    if (nova.visao) p.set("visao", nova.visao);
    if (nova.data) p.set("data", toDateKey(nova.data));
    window.history.replaceState(null, "", `${pathname}?${p}`);
    router.replace(`${pathname}?${p}`);
  }

  function passo(delta: number) {
    const { ancora: base, visao: v } = atual();
    irPara({ data: v === "mes" ? addMonths(base, delta) : addDays(base, delta * (v === "semana" ? 7 : 1)) });
  }

  function criar(dia: string, minutos: number) {
    if (!podeEscrever) return;
    setForm({ editando: null, prefill: { specificDate: dia, timeOfDay: horaTexto(minutos) } });
  }

  async function soltar(paraDia: string, minutos: number) {
    const atual = arraste;
    setArraste(null);
    setAlvo(null);
    if (!atual || !token) return;
    try {
      const agendamento = await apiRequest<Schedule>(`/schedules/${atual.item.schedule_id}`, { token });
      const mov = mover(agendamento, atual.deDia, paraDia, minutos);
      if (!mov.ok) {
        if (mov.motivo !== "Nada mudou.") toast({ title: "Não dá para mover", description: mov.motivo, kind: "warning" });
        return;
      }
      if (mov.serie) setConfirmar({ id: agendamento.id, mov });
      else await aplicar(agendamento.id, mov);
    } catch (err) {
      toast({ title: "Não foi possível mover", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function aplicar(id: number, mov: Extract<Movimento, { ok: true }>) {
    if (!token) return;
    try {
      await updateSchedule(token, id, mov.patch);
      toast({ title: "Agendamento movido", description: mov.depois, kind: "success" });
      setConfirmar(null);
      await calendario.refetch();
    } catch (err) {
      toast({ title: "Não foi possível mover", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const titulo = visao === "mes" ? monthLabel(ancora)
    : visao === "dia" ? `${ancora.getDate()} de ${ROTULO_MES[ancora.getMonth()]} de ${ancora.getFullYear()}`
    : intervalo(dias[0], dias[6]);

  return (
    <div className="flex flex-col gap-5" data-testid="agenda">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="mr-2">
          <p className="eyebrow">Agendamentos</p>
          <h1 className="titulo-condensado text-3xl" aria-live="polite">{titulo}</h1>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" onClick={() => irPara({ data: new Date() })}>Hoje</Button>
          <Button variant="ghost" size="icon" onClick={() => passo(-1)} aria-label="Anterior"><ChevronLeft className="h-5 w-5" /></Button>
          <Button variant="ghost" size="icon" onClick={() => passo(1)} aria-label="Próximo"><ChevronRight className="h-5 w-5" /></Button>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex rounded-lg border border-border bg-card p-1" role="tablist" aria-label="Visão do calendário">
            {VISOES.map((v) => (
              <button key={v.id} role="tab" aria-selected={visao === v.id} onClick={() => irPara({ visao: v.id })}
                className={cn("rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                  visao === v.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
                {v.rotulo}
              </button>
            ))}
          </div>
          {podeEscrever && (
            <Button onClick={() => setForm({ editando: null, prefill: { specificDate: toDateKey(new Date()) } })}>
              <Plus className="h-4 w-4" /> Criar
            </Button>
          )}
        </div>
      </header>

      {calendario.error && !calendario.data ? (
        <ErrorState message={calendario.error} onRetry={() => void calendario.refetch()} />
      ) : visao === "mes" ? (
        <GradeDoMes ancora={ancora} dias={dias} porDia={porDia} carregando={!calendario.data} podeEscrever={podeEscrever}
          arraste={arraste} alvo={alvo} setArraste={setArraste} setAlvo={setAlvo} soltar={soltar}
          abrir={(item, x, y) => setAberto({ item, x, y })} criar={(dia) => criar(dia, 8 * 60)}
          verDia={(d) => irPara({ visao: "dia", data: d })} />
      ) : (
        <GradeDeHoras key={visao} dias={dias} porDia={porDia} carregando={!calendario.data} podeEscrever={podeEscrever}
          arraste={arraste} alvo={alvo} setArraste={setArraste} setAlvo={setAlvo} soltar={soltar}
          abrir={(item, x, y) => setAberto({ item, x, y })} criar={criar} verDia={(d) => irPara({ visao: "dia", data: d })}
          vizinhos={visao === "dia" ? { anterior: () => passo(-1), proximo: () => passo(1) } : null} />
      )}

      {aberto && (
        <Cartao aberto={aberto} fechar={() => setAberto(null)} podeEscrever={podeEscrever} podeExecutar={podeExecutar}
          editar={(id) => { setAberto(null); setForm({ editando: id }); }}
          detalhes={(item) => { setAberto(null); setDetalhe(item); }}
          executou={() => void calendario.refetch()} />
      )}

      <Modal open={!!confirmar} onClose={() => setConfirmar(null)} title="Mudar o agendamento?" className="max-w-lg"
        description="É um agendamento que se repete: a mudança vale para todas as próximas vezes."
        footer={<>
          <Button variant="ghost" onClick={() => setConfirmar(null)}>Cancelar</Button>
          <Button onClick={() => confirmar && void aplicar(confirmar.id, confirmar.mov)}>Mudar todas</Button>
        </>}>
        {confirmar && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-base" data-testid="confirmar-mudanca">
            <dt className="text-muted-foreground">Antes</dt><dd className="line-through decoration-muted-foreground/60">{confirmar.mov.antes}</dd>
            <dt className="text-muted-foreground">Depois</dt><dd className="font-semibold text-titulo">{confirmar.mov.depois}</dd>
          </dl>
        )}
      </Modal>

      <ScheduleFormSheet open={!!form} onClose={() => setForm(null)} editingId={form?.editando ?? null} prefill={form?.prefill}
        automations={automacoes.data ?? []} flows={fluxos.data ?? []} onSaved={() => void calendario.refetch()} />
      <ScheduleDetailSheet scheduleId={detalhe?.schedule_id ?? null} item={detalhe} open={!!detalhe} onClose={() => setDetalhe(null)}
        automationById={new Map((automacoes.data ?? []).map((a) => [a.id, a]))} flowById={new Map((fluxos.data ?? []).map((f) => [f.id, f]))}
        onEdit={(id) => { setDetalhe(null); setForm({ editando: id }); }} onChanged={async () => { await calendario.refetch(); }}
        canWrite={podeEscrever} canTrigger={podeExecutar} />
    </div>
  );
}

function intervalo(a: Date, b: Date): string {
  if (a.getMonth() === b.getMonth()) return `${a.getDate()} – ${b.getDate()} de ${ROTULO_MES[a.getMonth()]} de ${b.getFullYear()}`;
  return `${a.getDate()} de ${ROTULO_MES[a.getMonth()]} – ${b.getDate()} de ${ROTULO_MES[b.getMonth()]} de ${b.getFullYear()}`;
}

/** Mês: um quadro por dia, com as primeiras ocorrências e "+N" para ver o dia inteiro. */
function GradeDoMes({ ancora, dias, porDia, carregando, podeEscrever, arraste, alvo, setArraste, setAlvo, soltar, abrir, criar, verDia }: Comum & {
  ancora: Date;
  dias: Date[];
  criar: (dia: string) => void;
  verDia: (d: Date) => void;
}) {
  const MAXIMO = 3;
  const clique = useRef<ReturnType<typeof setTimeout> | null>(null);
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="grade-do-mes">
      <div className="grid grid-cols-7 border-b border-border">
        {SEMANA.map((s) => <span key={s} className="py-3 text-center text-xs font-semibold tracking-wider text-muted-foreground">{s}</span>)}
      </div>
      <div className="grid grid-cols-7" style={{ gridAutoRows: "minmax(8.5rem, 1fr)" }}>
        {dias.map((d, i) => {
          const dia = toDateKey(d);
          const lista = [...(porDia.get(dia) ?? [])].sort((a, b) => a.inicio - b.inicio);
          const doMes = d.getMonth() === ancora.getMonth();
          const hoje = isSameDay(d, new Date());
          return (
            <div key={dia} data-dia={dia}
              className={cn("flex min-w-0 flex-col gap-1 border-border p-2", i % 7 !== 0 && "border-l", i >= 7 && "border-t",
                !doMes && "bg-muted/40", podeEscrever && "cursor-cell", alvo?.dia === dia && arraste && "bg-primary/10 ring-2 ring-inset ring-primary")}
              onClick={(ev) => {
                if (ev.target !== ev.currentTarget) return;
                // Espera um instante: se vier o segundo clique, abre o dia em vez de criar.
                if (clique.current) clearTimeout(clique.current);
                clique.current = setTimeout(() => { clique.current = null; criar(dia); }, 260);
              }}
              onDoubleClick={(ev) => {
                if (ev.target !== ev.currentTarget) return;
                if (clique.current) { clearTimeout(clique.current); clique.current = null; }
                verDia(d);
              }}
              title="Clique para criar · dois cliques para abrir o dia"
              onDragOver={(ev) => {
                if (!arraste) return;
                ev.preventDefault();
                const minutos = noFuso(arraste.item.planned_start, arraste.item.timezone || FUSO_PADRAO).minutos;
                if (alvo?.dia !== dia) setAlvo({ dia, minutos });
              }}
              onDrop={(ev) => { ev.preventDefault(); if (alvo) soltar(alvo.dia, alvo.minutos); }}>
              <button type="button" onClick={() => verDia(d)}
                className={cn("flex h-8 w-8 items-center justify-center self-center rounded-full text-sm font-semibold hover:bg-accent",
                  hoje ? "bg-primary text-primary-foreground hover:bg-primary" : doMes ? "text-titulo" : "text-muted-foreground")}>
                {d.getDate()}
              </button>
              {lista.slice(0, MAXIMO).map(({ item, inicio }) => {
                const arrastavel = podeEscrever && podeArrastar(item);
                return (
                  <button key={item.id} type="button" draggable={arrastavel} data-ocorrencia={item.schedule_id}
                    className={cn("flex min-w-0 items-center gap-1.5 truncate rounded px-1.5 py-0.5 text-left text-sm hover:bg-accent",
                      arrastavel ? "cursor-grab" : "cursor-pointer", arraste?.item.id === item.id && "opacity-40")}
                    onClick={(ev) => abrir(item, ev.clientX, ev.clientY)}
                    onDragStart={(ev) => { ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", item.id); setArraste({ item, deDia: dia, agarrouMin: 0 }); }}
                    onDragEnd={() => { setArraste(null); setAlvo(null); }}>
                    <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full", pontoDe(item))} />
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{horaTexto(inicio)}</span>
                    <span className="truncate">{nomeDe(item)}</span>
                  </button>
                );
              })}
              {lista.length > MAXIMO && (
                <button type="button" onClick={() => verDia(d)} className="px-1.5 text-left text-sm font-medium text-primary hover:underline">
                  + {lista.length - MAXIMO} mais
                </button>
              )}
            </div>
          );
        })}
      </div>
      {carregando && <p className="border-t border-border px-5 py-3 text-sm text-muted-foreground">Carregando…</p>}
    </section>
  );
}

/** O cartão que abre ao clicar numa ocorrência (como na agenda do Google). */
function Cartao({ aberto, fechar, podeEscrever, podeExecutar, editar, detalhes, executou }: {
  aberto: { item: ScheduleCalendarItem; x: number; y: number };
  fechar: () => void;
  podeEscrever: boolean;
  podeExecutar: boolean;
  editar: (id: number) => void;
  detalhes: (item: ScheduleCalendarItem) => void;
  executou: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const { item } = aberto;
  const agendamento = useApi<Schedule>(`/schedules/${item.schedule_id}`);
  const caixa = useRef<HTMLDivElement>(null);
  const situacao = temporalStatusMeta(item.temporal_status);
  const { minutos } = noFuso(item.actual_start ?? item.planned_start, item.timezone || FUSO_PADRAO);
  const data = new Date(item.planned_start);

  useEffect(() => {
    const tecla = (ev: KeyboardEvent) => ev.key === "Escape" && fechar();
    const fora = (ev: MouseEvent) => { if (caixa.current && !caixa.current.contains(ev.target as Node)) fechar(); };
    window.addEventListener("keydown", tecla);
    const t = setTimeout(() => window.addEventListener("mousedown", fora), 0);
    return () => { window.removeEventListener("keydown", tecla); window.removeEventListener("mousedown", fora); clearTimeout(t); };
  }, [fechar]);

  async function executarAgora() {
    if (!token) return;
    try {
      await triggerSchedule(token, item.schedule_id);
      toast({ title: "Pedido de execução enviado", kind: "success" });
      executou();
      fechar();
    } catch (err) {
      toast({ title: "Não foi possível executar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  const largura = 420;
  const left = Math.min(Math.max(aberto.x + 12, 16), (typeof window !== "undefined" ? window.innerWidth : 1920) - largura - 16);
  const top = Math.min(aberto.y - 20, (typeof window !== "undefined" ? window.innerHeight : 1080) - 300);
  return (
    <div ref={caixa} role="dialog" aria-label={nomeDe(item)} data-testid="cartao-ocorrencia"
      className="fixed z-50 animate-fade-in rounded-xl border border-border bg-popover p-5 shadow-xl" style={{ left, top: Math.max(top, 16), width: largura }}>
      <div className="mb-3 flex items-start gap-3">
        <span className={cn("mt-2 h-3 w-3 shrink-0 rounded-sm", pontoDe(item))} />
        <div className="min-w-0 flex-1">
          <p className="text-lg font-semibold leading-snug text-titulo">{nomeDe(item)}</p>
          {item.schedule_name && item.target_name !== item.schedule_name && <p className="truncate text-sm text-muted-foreground">{item.target_name}</p>}
        </div>
        <button onClick={fechar} aria-label="Fechar" className="rounded-md p-1 text-muted-foreground hover:bg-accent"><X className="h-4 w-4" /></button>
      </div>
      <dl className="space-y-2 text-sm">
        <div className="flex gap-3"><dt className="sr-only">Quando</dt>
          <dd>{data.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })} · {horaTexto(minutos)}</dd></div>
        <div className="flex items-center gap-2 text-muted-foreground"><Repeat className="h-4 w-4 shrink-0" />
          <dd>{agendamento.data ? descrever(agendamento.data) : "…"}{agendamento.data && agendamento.data.status === "paused" ? " · pausado" : ""}</dd></div>
        <div className="flex items-center gap-2"><span className={cn("h-2 w-2 rounded-full", situacao.dot)} /><dd>{situacao.label}</dd></div>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
        {podeEscrever && <Button size="sm" onClick={() => editar(item.schedule_id)}><Pencil className="h-4 w-4" /> Editar</Button>}
        {podeExecutar && <Button size="sm" variant="outline" onClick={() => void executarAgora()}><Play className="h-4 w-4" /> Executar agora</Button>}
        {item.execution_id
          ? <Button size="sm" variant="ghost" asChild><Link href={`/execucoes/${item.execution_id}`}>Acompanhar</Link></Button>
          : <Button size="sm" variant="ghost" onClick={() => detalhes(item)}>Detalhes</Button>}
      </div>
    </div>
  );
}
