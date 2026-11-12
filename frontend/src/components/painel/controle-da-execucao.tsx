"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { AlertOctagon, CircleStop, Hourglass, Loader2, PauseCircle, Play, Power, Square, Unplug, WifiOff } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { PAUSAS } from "@/lib/acompanhar";
import { horario, relativo } from "@/lib/fila";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

/*
 * Parar e continuar uma execução (12/11/2026) e a linha única que diz por que ela não está
 * andando: cancelando, parando depois do item, pausa, espera ou sem sinal. Rodando normal não
 * mostra nada, para o Painel não ficar poluído.
 */

export type SituacaoDoAgora =
  | { tipo: "cancelamento_sem_resposta"; desde: string | null; recebido: boolean }
  | { tipo: "sem_comunicacao"; desde: string | null; cancela_em: string | null }
  | { tipo: "cancelando" | "parando"; desde: string | null; recebido: boolean }
  | { tipo: "pausa"; motivo: string | null; detalhe: string | null; desde: string | null }
  | { tipo: "espera"; rotulo: string | null; desde: string | null }
  | { tipo: "sem_sinal"; desde: string | null };

export function textoDaSituacao(s: SituacaoDoAgora): { texto: string; tom: string; Icone: typeof Square } {
  const ha = s.desde ? ` · ${relativo(s.desde)}` : "";
  switch (s.tipo) {
    case "cancelamento_sem_resposta":
      return { texto: s.recebido ? "Recebeu o cancelamento e não parou em 2 min"
                                 : "Não recebeu o cancelamento em 2 min",
               tom: "text-destructive-foreground bg-destructive", Icone: AlertOctagon };
    case "sem_comunicacao":
      return { texto: `Comunicação não está ativa: tentando${s.cancela_em ? ` até ${horario(s.cancela_em)}, depois cancela` : ""}`,
               tom: "text-destructive bg-destructive/10", Icone: Unplug };
    case "cancelando":
      return { texto: s.recebido ? "Cancelando: a automação está encerrando" : "Cancelamento pedido: esperando a automação receber",
               tom: "text-destructive bg-destructive/10", Icone: Loader2 };
    case "parando":
      return { texto: s.recebido ? "Para ao terminar o item atual" : "Parada pedida: esperando a automação receber",
               tom: "text-warning bg-warning/10", Icone: CircleStop };
    case "pausa":
      return { texto: `${PAUSAS[s.motivo ?? ""] ?? "Pausada"}${s.detalhe ? `: ${s.detalhe}` : ""}${ha}`,
               tom: "text-info bg-info/10", Icone: PauseCircle };
    case "espera":
      return { texto: `Esperando${s.rotulo ? `: ${s.rotulo}` : ""}${ha}`, tom: "text-info bg-info/10", Icone: Hourglass };
    case "sem_sinal":
      return { texto: `Sem sinal da automação${s.desde ? ` ${relativo(s.desde)}` : ""}`,
               tom: "text-warning bg-warning/10", Icone: WifiOff };
  }
}

export function LinhaDaSituacao({ situacao, className }: { situacao: SituacaoDoAgora | null | undefined; className?: string }) {
  if (!situacao) return null;
  const { texto, tom, Icone } = textoDaSituacao(situacao);
  return (
    <p className={cn("flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium", tom, className)}
      data-testid="situacao" data-situacao={situacao.tipo} title={texto}>
      <Icone className={cn("h-4 w-4 shrink-0", situacao.tipo === "cancelando" && "animate-spin")} />
      <span className="line-clamp-2">{texto}</span>
    </p>
  );
}

/** A janela vai para o fim da página: dentro do cartão ela ficaria atrás dos outros cartões. */
function NoTopo({ children }: { children: ReactNode }) {
  const [pronto, setPronto] = useState(false);
  useEffect(() => setPronto(true), []);
  return pronto ? createPortal(children, document.body) : null;
}

function useAcao() {
  const { token } = useAuth();
  const { toast } = useToast();
  const [ocupado, setOcupado] = useState(false);
  async function rodar<T>(caminho: string, corpo: unknown, sucesso: string): Promise<T | null> {
    setOcupado(true);
    try {
      const r = await apiRequest<T>(caminho, { token, method: "POST", body: JSON.stringify(corpo ?? {}) });
      toast({ title: sucesso, kind: "success" });
      return r;
    } catch (err) {
      toast({ title: "Não foi possível concluir", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return null;
    } finally {
      setOcupado(false);
    }
  }
  return { rodar, ocupado };
}

/** "Parar": escolher entre terminar o item atual ou cancelar agora. No modo agente só "agora". */
/** "Encerrar no Portal": só quando o cancelamento ficou 2 min sem resposta. */
export function BotaoEncerrar({ execucaoId, recebido, aoEncerrar, grande = false }: {
  execucaoId: string; recebido: boolean; aoEncerrar?: () => void; grande?: boolean;
}) {
  const [aberto, setAberto] = useState(false);
  const { rodar, ocupado } = useAcao();
  return (
    <>
      <Button size={grande ? "md" : "sm"} variant="destructive" className={cn(!grande && "h-8 px-2.5")}
        onClick={(ev) => { ev.preventDefault(); ev.stopPropagation(); setAberto(true); }} aria-label="Encerrar no Portal">
        <Power className="h-3.5 w-3.5" /> Encerrar
      </Button>
      <NoTopo>
        <Modal open={aberto} onClose={() => setAberto(false)} title="Encerrar no Portal?"
          description={recebido ? "A automação recebeu o cancelamento há mais de 2 min e não parou."
            : "A automação não recebeu o cancelamento em 2 min."}
          footer={<>
            <Button variant="ghost" onClick={() => setAberto(false)}>Voltar</Button>
            <Button variant="destructive" disabled={ocupado} onClick={async () => {
              const ok = await rodar(`/fila/execucoes/${execucaoId}/encerrar`, {}, "Execução encerrada no Portal");
              if (ok) { setAberto(false); aoEncerrar?.(); }
            }}>Encerrar no Portal</Button>
          </>}>
          <ul className="list-disc space-y-1.5 pl-5 text-sm">
            <li>A execução fica como <strong>cancelada com erro</strong> e a máquina é liberada para a fila.</li>
            <li>A automação perde o acesso ao Portal. Com o SDK 0.4.0 ela se encerra sozinha ao perceber.</li>
            <li>O programa pode ter ficado aberto na máquina: confira antes de rodar de novo.</li>
            <li>Os itens que faltaram podem ser refeitos com Continuar.</li>
          </ul>
        </Modal>
      </NoTopo>
    </>
  );
}

export function BotaoParar({ execucaoId, modo, situacao, aoParar, grande = false }: {
  execucaoId: string; modo: string | null; situacao?: SituacaoDoAgora | null; aoParar?: () => void; grande?: boolean;
}) {
  const [aberto, setAberto] = useState(false);
  const soAgora = modo === "agent";
  const jaParando = situacao?.tipo === "parando";
  const [escolha, setEscolha] = useState<"apos_item" | "agora">(soAgora || jaParando ? "agora" : "apos_item");
  const { rodar, ocupado } = useAcao();
  if (situacao?.tipo === "cancelando" || situacao?.tipo === "cancelamento_sem_resposta") return null;  // já está encerrando

  const opcoes = [
    { valor: "apos_item" as const, titulo: "Parar depois do item atual",
      texto: "Termina o item que está rodando e não começa outro. Nada fica pela metade.", some: soAgora || jaParando },
    { valor: "agora" as const, titulo: "Cancelar agora",
      texto: soAgora ? "O Agent encerra a automação. O item em andamento fica interrompido."
        : "A automação interrompe o quanto antes. O item em andamento fica interrompido e pode ser refeito ao continuar.",
      some: false },
  ].filter((o) => !o.some);

  return (
    <>
      <Button size={grande ? "md" : "sm"} variant="outline" onClick={(ev) => { ev.preventDefault(); ev.stopPropagation(); setAberto(true); }}
        aria-label="Parar a execução" className={cn(!grande && "h-8 px-2.5")}>
        <Square className="h-3.5 w-3.5 fill-current" /> Parar
      </Button>
      <NoTopo>
      <Modal open={aberto} onClose={() => setAberto(false)} title="Parar a execução?"
        description="Itens que não terminarem podem ser refeitos depois com Continuar."
        footer={<>
          <Button variant="ghost" onClick={() => setAberto(false)}>Voltar</Button>
          <Button variant={escolha === "agora" ? "destructive" : "primary"} disabled={ocupado}
            onClick={async () => {
              const ok = await rodar(`/fila/execucoes/${execucaoId}/parar`, { modo: escolha },
                escolha === "agora" ? "Cancelamento pedido" : "A execução para depois do item atual");
              if (ok) { setAberto(false); aoParar?.(); }
            }}>
            {escolha === "agora" ? "Cancelar agora" : "Parar depois do item"}
          </Button>
        </>}>
        <div className="space-y-2" role="radiogroup" aria-label="Como parar">
          {opcoes.map((o) => (
            <label key={o.valor} className={cn("flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors",
              escolha === o.valor ? "border-primary bg-primary/5" : "border-border hover:bg-muted")}>
              <input type="radio" name="como-parar" className="mt-1" checked={escolha === o.valor} onChange={() => setEscolha(o.valor)} />
              <span>
                <span className="block font-semibold text-titulo">{o.titulo}</span>
                <span className="block text-sm text-muted-foreground">{o.texto}</span>
              </span>
            </label>
          ))}
        </div>
      </Modal>
      </NoTopo>
    </>
  );
}

type Previa = {
  pode: boolean; motivo: string | null; continuada_em: string | null; pular: number; sem_itens: boolean;
  refazer: Array<{ chave: string; rotulo: string | null; situacao: string }>;
};

const SITUACAO_DO_ITEM: Record<string, string> = {
  pendente: "não começou", executando: "interrompido", cancelado: "interrompido", erro: "deu erro",
};

/** "Continuar": abre a prévia (o que roda de novo e o que é pulado) e cria a execução nova. */
export function BotaoContinuar({ execucaoId, size = "sm" }: { execucaoId: string; size?: "sm" | "md" }) {
  const router = useRouter();
  const [aberto, setAberto] = useState(false);
  const previa = useApi<Previa>(aberto ? `/fila/execucoes/${execucaoId}/continuar` : null);
  const { rodar, ocupado } = useAcao();
  const p = previa.data;
  return (
    <>
      <Button size={size} variant="outline" onClick={() => setAberto(true)} data-testid="continuar">
        <Play className="h-4 w-4" /> Continuar
      </Button>
      <NoTopo>
      <Modal open={aberto} onClose={() => setAberto(false)} title="Continuar de onde parou?"
        footer={<>
          <Button variant="ghost" onClick={() => setAberto(false)}>Voltar</Button>
          <Button disabled={!p?.pode || ocupado} onClick={async () => {
            const r = await rodar<{ execution_id: string | null }>(`/fila/execucoes/${execucaoId}/continuar`, {}, "Execução continuada: entrou na fila");
            if (r) {
              setAberto(false);
              if (r.execution_id) router.push(`/execucoes/${r.execution_id}`);
            }
          }}>Continuar</Button>
        </>}>
        {!p ? (
          previa.error ? <p className="text-sm text-destructive">{previa.error}</p> : <div className="skeleton h-24 rounded-lg" />
        ) : !p.pode ? (
          <p className="text-sm">{p.motivo}</p>
        ) : p.sem_itens ? (
          <p className="text-sm">A execução entra na fila de novo, com os mesmos parâmetros.</p>
        ) : (
          <div className="space-y-3 text-sm" data-testid="previa-continuar">
            <p>
              Uma execução nova entra na fila só com <strong>{p.refazer.length} {p.refazer.length === 1 ? "item" : "itens"}</strong>
              {p.pular > 0 && <> e pula {p.pular === 1 ? "o que já deu certo" : `os ${p.pular} que já deram certo`}</>}.
              A automação recebe o que já tinha sido feito em cada item.
            </p>
            <ul className="max-h-56 divide-y divide-border overflow-y-auto rounded-lg border border-border">
              {p.refazer.map((i) => (
                <li key={i.chave} className="flex items-baseline justify-between gap-3 px-3 py-2">
                  <span className="truncate"><span className="tabular-nums text-muted-foreground">{i.chave}</span> {i.rotulo}</span>
                  <span className={cn("shrink-0 text-xs", i.situacao === "erro" ? "text-destructive" : "text-muted-foreground")}>
                    {SITUACAO_DO_ITEM[i.situacao] ?? i.situacao}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Modal>
      </NoTopo>
    </>
  );
}
