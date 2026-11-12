"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";

import { horaTexto, lado, noFuso, noPasso } from "@/lib/agenda";
import { addDays, isSameDay, toDateKey } from "@/lib/calendar";
import { cn } from "@/lib/utils";
import { SEMANA, corDe, duracaoMin, nomeDe, podeArrastar, type Comum } from "@/components/schedules/agenda/agenda-comum";
import { Button } from "@/components/ui/button";
import type { ScheduleCalendarItem } from "@/types/schedule";

const CHAVE_ZOOM = "portal.agenda.hora";
export const ZOOM_MIN = 32;
export const ZOOM_MAX = 240;

/** Altura de uma hora, em px. Sem escolha salva, cabe das 8 h às 18 h na área visível. */
function useAlturaDaHora(caixa: React.RefObject<HTMLDivElement | null>) {
  const [hora, setHora] = useState<number | null>(null);
  useEffect(() => {
    let salva: number | null = null;
    try {
      salva = Number(window.localStorage.getItem(CHAVE_ZOOM)) || null;
    } catch {
      salva = null;
    }
    const visivel = caixa.current?.clientHeight ?? 700;
    setHora(salva ?? Math.min(Math.max(Math.round(visivel / 10.5), 48), ZOOM_MAX));
  }, [caixa]);
  function mudar(nova: number) {
    const valor = Math.min(Math.max(Math.round(nova), ZOOM_MIN), ZOOM_MAX);
    setHora(valor);
    try {
      window.localStorage.setItem(CHAVE_ZOOM, String(valor));
    } catch {
      /* sem armazenamento: vale só nesta tela */
    }
  }
  return { hora: hora ?? 64, mudar, pronta: hora !== null };
}

type Selecao = { dia: string; de: number; ate: number };

const rotuloDoDia = (d: Date) => `${SEMANA[(d.getDay() + 6) % 7]} ${d.getDate()}`;

/**
 * Dia e Semana: grade de horas. Clique (ou clique e arraste) num espaço vazio para criar;
 * Ctrl + roda do mouse estica ou encolhe as horas; o dia do cabeçalho abre a visão Dia. Abre
 * das 8 h às 18 h; no dia de hoje, 1 h 30 antes do agora.
 */
export function GradeDeHoras({ dias, porDia, carregando, podeEscrever, arraste, alvo, setArraste, setAlvo, soltar, abrir, criar, verDia, vizinhos }: Comum & {
  dias: Date[];
  criar: (dia: string, minutos: number) => void;
  verDia: (d: Date) => void;
  vizinhos?: { anterior: () => void; proximo: () => void } | null;
}) {
  const rolagem = useRef<HTMLDivElement>(null);
  const { hora, mudar, pronta } = useAlturaDaHora(rolagem);
  const [agora, setAgora] = useState(() => noFuso(new Date().toISOString()));
  const [selecao, setSelecao] = useState<Selecao | null>(null);
  useEffect(() => {
    const t = setInterval(() => setAgora(noFuso(new Date().toISOString())), 60000);
    return () => clearInterval(t);
  }, []);

  const temHoje = dias.some((d) => isSameDay(d, new Date()));
  useEffect(() => {
    const caixa = rolagem.current;
    if (!caixa || !pronta) return;
    const inicioMin = temHoje ? Math.max(agora.minutos - 90, 0) : 8 * 60;
    caixa.scrollTop = (inicioMin / 60) * hora;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pronta, dias.length, toDateKey(dias[0])]);

  // Ctrl + roda: zoom das horas, mantendo parada a hora que está sob o mouse.
  const zoom = useRef({ hora, mudar });
  zoom.current = { hora, mudar };
  useEffect(() => {
    const caixa = rolagem.current;
    if (!caixa) return;
    const roda = (ev: WheelEvent) => {
      if (!ev.ctrlKey) return;
      ev.preventDefault();
      const { hora: atual, mudar: aplicar } = zoom.current;
      const y = ev.clientY - caixa.getBoundingClientRect().top;
      const horaSobMouse = (caixa.scrollTop + y) / atual;
      const nova = Math.round(Math.min(Math.max(atual * (ev.deltaY < 0 ? 1.15 : 1 / 1.15), ZOOM_MIN), ZOOM_MAX));
      aplicar(nova);
      requestAnimationFrame(() => {
        caixa.scrollTop = horaSobMouse * nova - y;
      });
    };
    caixa.addEventListener("wheel", roda, { passive: false });
    return () => caixa.removeEventListener("wheel", roda);
  }, []);

  const colunas = { gridTemplateColumns: `4.5rem repeat(${dias.length}, minmax(0, 1fr))${vizinhos ? " 4.5rem" : ""}` };
  const px = (minutos: number) => (minutos / 60) * hora;
  const minutosDoPonteiro = (ev: { clientY: number; currentTarget: EventTarget }) => {
    const r = (ev.currentTarget as HTMLElement).getBoundingClientRect();
    return ((ev.clientY - r.top) / r.height) * 1440;
  };

  function comecarSelecao(ev: React.MouseEvent, dia: string) {
    if (!podeEscrever || ev.button !== 0 || ev.target !== ev.currentTarget) return;
    ev.preventDefault();
    const r = (ev.currentTarget as HTMLElement).getBoundingClientRect();
    const em = (y: number) => Math.min(Math.max(((y - r.top) / r.height) * 1440, 0), 1440);
    const inicio = Math.floor(em(ev.clientY) / 30) * 30;
    let atual: Selecao = { dia, de: inicio, ate: inicio + 30 };
    setSelecao(atual);
    const mover = (e: MouseEvent) => {
      const ponto = em(e.clientY);
      atual = { dia, de: Math.min(inicio, Math.floor(ponto / 15) * 15), ate: Math.max(inicio + 30, Math.ceil(ponto / 15) * 15) };
      setSelecao(atual);
    };
    const soltarMouse = () => {
      window.removeEventListener("mousemove", mover);
      window.removeEventListener("mouseup", soltarMouse);
      setSelecao(null);
      criar(atual.dia, atual.de);
    };
    window.addEventListener("mousemove", mover);
    window.addEventListener("mouseup", soltarMouse);
  }

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="grade-de-horas">
      <div className="grid border-b border-border" style={colunas}>
        <div className="flex items-center justify-center">
          {vizinhos && (
            <button type="button" onClick={vizinhos.anterior} aria-label="Dia anterior" data-testid="dia-anterior"
              className="flex flex-col items-center gap-0.5 rounded-lg px-2 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
              <ChevronLeft className="h-5 w-5" />
              <span className="text-xs font-semibold">{rotuloDoDia(addDays(dias[0], -1))}</span>
            </button>
          )}
        </div>
        {dias.map((d) => {
          const hoje = isSameDay(d, new Date());
          return (
            <button key={toDateKey(d)} type="button" onClick={() => verDia(d)} disabled={!!vizinhos}
              title={vizinhos ? undefined : "Abrir o dia"} data-cabecalho={toDateKey(d)}
              className="flex flex-col items-center gap-1 border-l border-border py-3 transition-colors enabled:hover:bg-accent/60">
              <span className={cn("text-xs font-semibold tracking-wider", hoje ? "text-primary" : "text-muted-foreground")}>{SEMANA[(d.getDay() + 6) % 7]}</span>
              <span className={cn("flex h-11 w-11 items-center justify-center rounded-full text-2xl",
                hoje ? "bg-primary font-semibold text-primary-foreground" : "text-titulo")}>{d.getDate()}</span>
            </button>
          );
        })}
        {vizinhos && (
          <div className="flex items-center justify-center border-l border-border">
            <button type="button" onClick={vizinhos.proximo} aria-label="Próximo dia" data-testid="dia-seguinte"
              className="flex flex-col items-center gap-0.5 rounded-lg px-2 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
              <ChevronRight className="h-5 w-5" />
              <span className="text-xs font-semibold">{rotuloDoDia(addDays(dias[0], 1))}</span>
            </button>
          </div>
        )}
      </div>
      <div ref={rolagem} className="max-h-[calc(100vh-23rem)] min-h-[24rem] overflow-y-auto" data-testid="rolagem-horas">
        <div className="relative grid select-none" style={{ ...colunas, height: `${24 * hora}px` }} data-altura-hora={hora}>
          <div className="relative">
            {Array.from({ length: 23 }, (_, h) => h + 1).map((h) => (
              <span key={h} className="absolute right-3 -translate-y-1/2 text-xs tabular-nums text-muted-foreground" style={{ top: `${h * hora}px` }}>
                {String(h).padStart(2, "0")}:00
              </span>
            ))}
          </div>
          {dias.map((d) => {
            const dia = toDateKey(d);
            const blocos = lado(porDia.get(dia) ?? []);
            const hoje = isSameDay(d, new Date());
            return (
              <div key={dia} data-dia={dia}
                className={cn("relative border-l border-border", podeEscrever && "cursor-cell")}
                style={{ backgroundImage: `linear-gradient(to bottom, hsl(var(--border)) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--border) / 0.4) 1px, transparent 1px)`,
                  backgroundSize: `100% ${hora}px, 100% ${hora / 2}px` }}
                onMouseDown={(ev) => comecarSelecao(ev, dia)}
                onDragOver={(ev) => {
                  if (!arraste) return;
                  ev.preventDefault();
                  ev.dataTransfer.dropEffect = "move";
                  const minutos = noPasso(minutosDoPonteiro(ev) - arraste.agarrouMin);
                  if (alvo?.dia !== dia || alvo.minutos !== minutos) setAlvo({ dia, minutos });
                }}
                onDrop={(ev) => {
                  ev.preventDefault();
                  if (alvo) soltar(alvo.dia, alvo.minutos);
                }}>
                {blocos.map(({ item: bruto, inicio, fim, coluna, colunas: total }) => {
                  const item = bruto as ScheduleCalendarItem;
                  const arrastavel = podeEscrever && podeArrastar(item);
                  const largura = 100 / total;
                  return (
                    <button key={item.id} type="button" draggable={arrastavel} data-ocorrencia={item.schedule_id}
                      title={`${nomeDe(item)} · ${horaTexto(inicio)}`}
                      className={cn("absolute overflow-hidden rounded-md border-l-4 px-2 py-1 text-left shadow-sm transition-opacity hover:z-10 hover:shadow-md focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        corDe(item), arrastavel ? "cursor-grab active:cursor-grabbing" : "cursor-pointer",
                        arraste?.item.id === item.id && "opacity-40")}
                      style={{ top: `${px(inicio)}px`, height: `${Math.max(px(fim - inicio) - 2, 18)}px`,
                        left: `calc(${coluna * largura}% + 2px)`, width: `calc(${largura}% - 6px)` }}
                      onClick={(ev) => abrir(item, ev.clientX, ev.clientY)}
                      onDragStart={(ev) => {
                        const r = ev.currentTarget.getBoundingClientRect();
                        ev.dataTransfer.effectAllowed = "move";
                        ev.dataTransfer.setData("text/plain", item.id);
                        setArraste({ item, deDia: dia, agarrouMin: ((ev.clientY - r.top) / r.height) * (fim - inicio) });
                      }}
                      onDragEnd={() => {
                        setArraste(null);
                        setAlvo(null);
                      }}>
                      <span className="block truncate text-sm font-semibold leading-tight">{nomeDe(item)}</span>
                      {px(fim - inicio) >= 40 && <span className="block truncate text-xs opacity-80">{horaTexto(inicio)} – {horaTexto(fim)}</span>}
                    </button>
                  );
                })}
                {selecao?.dia === dia && (
                  <div className="pointer-events-none absolute inset-x-1 z-20 rounded-md bg-primary/85 px-2 py-1 text-sm font-semibold text-primary-foreground shadow-md"
                    data-testid="selecao-de-horario" style={{ top: `${px(selecao.de)}px`, height: `${px(selecao.ate - selecao.de)}px` }}>
                    {horaTexto(selecao.de)} – {horaTexto(selecao.ate)}
                  </div>
                )}
                {arraste && alvo?.dia === dia && (
                  <div className="pointer-events-none absolute inset-x-1 z-20 rounded-md border-2 border-dashed border-primary bg-primary/10 px-2 py-1 text-sm font-semibold text-primary"
                    data-testid="destino-do-arraste" style={{ top: `${px(alvo.minutos)}px`, height: `${px(duracaoMin(arraste.item))}px` }}>
                    {horaTexto(alvo.minutos)}
                  </div>
                )}
                {hoje && agora.dia === dia && (
                  <div className="pointer-events-none absolute inset-x-0 z-10 flex items-center" style={{ top: `${px(agora.minutos)}px` }}>
                    <span className="-ml-1.5 h-3 w-3 rounded-full bg-destructive" />
                    <span className="h-0.5 flex-1 bg-destructive" />
                  </div>
                )}
              </div>
            );
          })}
          {vizinhos && <div className="border-l border-border" />}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-2 text-sm text-muted-foreground">
        <span>{carregando ? "Carregando…" : "Clique ou arraste num horário vazio para criar · Ctrl + roda do mouse estica ou encolhe as horas"}</span>
        <span className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Encolher as horas" onClick={() => mudar(hora / 1.25)}><Minus className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" aria-label="Esticar as horas" onClick={() => mudar(hora * 1.25)}><Plus className="h-4 w-4" /></Button>
        </span>
      </div>
    </section>
  );
}
