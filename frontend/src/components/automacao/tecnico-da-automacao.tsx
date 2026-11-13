"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { CalendarClock, Check, Copy, GitBranch, KeyRound, Monitor, RotateCw, ShieldCheck, Webhook, X } from "lucide-react";

import { AutomationVersionsPanel } from "@/components/automations/automation-versions-panel";
import { SituacaoDoSegredo, type Segredo } from "@/components/secrets/secrets-manager";
import { DetailJson } from "@/components/shared/detail-json";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { PriorityBadge } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { describeRecurrence } from "@/lib/cron";
import { relativo } from "@/lib/fila";
import { podeGerenciar, podeVer } from "@/lib/permissions";
import { executorLabel } from "@/lib/status";
import { formatDuration } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { AutomationSource } from "@/types/automation-import";
import type { Schedule } from "@/types/schedule";
import type { Trigger } from "@/types/trigger";

/*
 * Aba Técnico da automação (12/11/2026): só o que faz sentido hoje, em blocos.
 * 1. Versões e publicação (com a origem do pacote).
 * 2. Como roda e onde (as instâncias diretas nas máquinas).
 * 3. Disparos automáticos (agendamentos e webhooks).
 * 4. Segredos que usa (13/11/2026): senhas que a automação pede com a.segredo("chave").
 * 5. Acessos: o normal é pelo time; aqui ficam as exceções.
 * 6. Para quem desenvolve (recolhido).
 * Saíram "Preferência de workers" e "Workers disponíveis": o despacho pela Fila não usa mais.
 */

type Instancia = { id: string; status: string; automation_id: number; nome_informado: string | null; versao: string | null;
  maquina_id: string | null; maquina_nome: string | null; ultimo_sinal: string | null };

const SITUACAO_DA_INSTANCIA: Record<string, { texto: string; tom: "success" | "warning" | "neutral" | "destructive" }> = {
  aprovada: { texto: "Aprovada", tom: "success" }, pendente: { texto: "Esperando aprovação", tom: "warning" },
  quarentena: { texto: "Em quarentena", tom: "warning" }, revogada: { texto: "Revogada", tom: "neutral" },
};

function Bloco({ titulo, icone, acao, children, testid }: { titulo: string; icone: ReactNode; acao?: ReactNode; children: ReactNode; testid?: string }) {
  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-sm" data-testid={testid}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-titulo">{icone} {titulo}</h3>
        {acao}
      </div>
      {children}
    </section>
  );
}

function Dado({ rotulo, valor }: { rotulo: string; valor: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{rotulo}</dt>
      <dd className="mt-1 font-medium">{valor}</dd>
    </div>
  );
}

export function TecnicoDaAutomacao({ id }: { id: string }) {
  const { token, user } = useAuth();
  const { toast } = useToast();
  const automacao = useApi<Automation>(`/automations/${id}`);
  const origens = useApi<AutomationSource[]>(`/automations/${id}/sources`);
  const gatilhos = useApi<Trigger[]>("/triggers");
  const agendamentos = useApi<Schedule[]>("/schedules");
  const instancias = useApi<{ instancias: Instancia[] }>("/instancias-diretas");

  if (!automacao.data) return <div className="skeleton h-64 rounded-xl" />;
  const a = automacao.data;
  const numero = Number(id);
  const meusGatilhos = (Array.isArray(gatilhos.data) ? gatilhos.data : []).filter((g) => g.automation_id === numero);
  const meusAgendamentos = (Array.isArray(agendamentos.data) ? agendamentos.data : []).filter((s) => s.automation_id === numero);
  const minhasInstancias = (Array.isArray(instancias.data?.instancias) ? instancias.data.instancias : []).filter((i) => i.automation_id === numero);
  const listaDeOrigens = Array.isArray(origens.data) ? origens.data : [];

  async function verificarAtualizacao() {
    try {
      const r = await apiRequest<{ update_available?: boolean }>(`/automations/${id}:sync`, { method: "POST", token });
      toast({ title: r.update_available ? "Há uma versão nova no GitHub" : "Já está na versão mais nova", kind: r.update_available ? "info" : "success" });
      await origens.refetch();
    } catch (err) {
      toast({ title: "Não foi possível verificar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]" data-testid="tecnico">
      <div className="min-w-0 space-y-6">
        <Bloco titulo="Versões e publicação" icone={<GitBranch className="h-5 w-5 text-primary" />} testid="tecnico-versoes"
          acao={listaDeOrigens.some((o) => o.type === "github") && (
            <Button size="sm" variant="outline" onClick={() => void verificarAtualizacao()}><RotateCw className="h-4 w-4" /> Verificar atualização</Button>
          )}>
          <p className="text-sm text-muted-foreground">
            Origem do pacote: {listaDeOrigens.length === 0 ? "cadastrada à mão, sem importação." : listaDeOrigens.map((o) => (
              o.type === "github" ? `GitHub ${o.owner}/${o.repository} @ ${o.branch}${o.sync_status === "update_available" ? " (há versão nova)" : ""}`
                : `upload de ${o.original_filename}`)).join("; ")}
          </p>
          <AutomationVersionsPanel automation={a} />
        </Bloco>

        <Bloco titulo="Como roda" icone={<Monitor className="h-5 w-5 text-primary" />} testid="tecnico-como-roda"
          acao={<Link href="/maquinas" className="text-sm font-medium text-primary hover:underline">Gerenciar em Máquinas</Link>}>
          <dl className="grid gap-4 sm:grid-cols-4">
            <Dado rotulo="Tipo" valor={executorLabel(a.executor_type)} />
            <Dado rotulo="Prioridade padrão" valor={<PriorityBadge priority={a.default_priority} />} />
            <Dado rotulo="Tempo limite" valor={formatDuration(a.timeout_seconds)} />
            <Dado rotulo="Tentativas extras" valor={<span className="tabular-nums">{a.max_retries}</span>} />
          </dl>
          <div className="space-y-2 border-t border-border pt-3">
            <p className="text-sm font-medium">Onde roda (automação direta nas máquinas)</p>
            {instancias.error ? (
              <p className="text-sm text-muted-foreground">Só quem gerencia máquinas vê as instâncias.</p>
            ) : minhasInstancias.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma máquina inscrita para esta automação.</p>
            ) : (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {minhasInstancias.map((i) => {
                  const s = SITUACAO_DA_INSTANCIA[i.status] ?? { texto: i.status, tom: "neutral" as const };
                  return (
                    <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                      <span className="font-medium">{i.maquina_nome ?? i.nome_informado ?? i.id}</span>
                      <span className="text-muted-foreground">{i.versao ? `versão ${i.versao}` : ""}{i.ultimo_sinal ? ` · sinal ${relativo(i.ultimo_sinal)}` : ""}</span>
                      <Badge tone={s.tom}>{s.texto}</Badge>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </Bloco>

        <details className="rounded-xl border border-border bg-card p-5 shadow-sm" data-testid="tecnico-dev">
          <summary className="cursor-pointer text-lg font-semibold text-titulo">Para quem desenvolve</summary>
          <dl className="mt-4 grid gap-4 sm:grid-cols-3">
            <Dado rotulo="ID" valor={<span className="tabular-nums">{a.id}</span>} />
            {a.key && <Dado rotulo="Chave" valor={<span className="font-mono text-sm">{a.key}</span>} />}
            <Dado rotulo="Slug" valor={<span className="font-mono text-sm">{a.slug}</span>} />
          </dl>
          <div className="mt-4"><DetailJson data={a} /></div>
        </details>
      </div>

      <div className="min-w-0 space-y-6">
        <Bloco titulo="Disparos automáticos" icone={<CalendarClock className="h-5 w-5 text-primary" />} testid="tecnico-disparos"
          acao={<Link href="/schedules" className="text-sm font-medium text-primary hover:underline">Agenda</Link>}>
          {meusAgendamentos.length === 0 && meusGatilhos.length === 0 && (
            <p className="text-sm text-muted-foreground">Roda só quando alguém pede.</p>
          )}
          {meusAgendamentos.length > 0 && (
            <ul className="space-y-1.5 text-sm">
              {meusAgendamentos.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2">
                  <span>{describeRecurrence(s)}</span>
                  <Badge tone={s.is_active ? "success" : "neutral"}>{s.is_active ? "Ligado" : "Desligado"}</Badge>
                </li>
              ))}
            </ul>
          )}
          {meusGatilhos.length > 0 && (
            <ul className="space-y-2 border-t border-border pt-3 text-sm">
              {meusGatilhos.map((g) => <Gatilho key={g.id} gatilho={g} />)}
            </ul>
          )}
        </Bloco>

        {podeVer(user, "segredos") && <SegredosQueUsa id={id} gerencia={podeGerenciar(user, "segredos")} />}

        <Bloco titulo="Acessos" icone={<ShieldCheck className="h-5 w-5 text-primary" />} testid="tecnico-acessos">
          <p className="text-sm text-muted-foreground">
            Quem vê e executa esta automação vem dos <Link href="/teams" className="text-primary hover:underline">times</Link> (pela
            categoria). Aqui ficam só as exceções, para uma pessoa ou um time.
          </p>
          <Button variant="outline" asChild><Link href={`/automations/${id}/acessos`}><ShieldCheck className="h-4 w-4" /> Exceções de acesso</Link></Button>
        </Bloco>
      </div>
    </div>
  );
}

function Gatilho({ gatilho }: { gatilho: Trigger }) {
  const [copiado, setCopiado] = useState(false);
  if (gatilho.trigger_type === "chained") {
    return <li><Badge tone="primary">em cadeia</Badge> <span className="text-muted-foreground">roda quando a automação de origem termina ({gatilho.condition ?? "success"})</span></li>;
  }
  return (
    <li className="flex items-center gap-2">
      <Badge tone="info"><Webhook className="h-3 w-3" /> {gatilho.trigger_type}</Badge>
      <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">{gatilho.route_path}</span>
      <button type="button" aria-label="Copiar o endereço" className="text-muted-foreground hover:text-foreground"
        onClick={() => { void navigator.clipboard.writeText(gatilho.route_path).then(() => { setCopiado(true); setTimeout(() => setCopiado(false), 1500); }).catch(() => undefined); }}>
        {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
    </li>
  );
}

type SegredoDaAutomacao = { id: string; chave: string; nome: string; situacao: string; vencido: boolean; ultimo_uso: string | null };

function SegredosQueUsa({ id, gerencia }: { id: string; gerencia: boolean }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const meus = useApi<{ segredos: SegredoDaAutomacao[] }>(`/segredos/da-automacao/${id}`);
  const todos = useApi<{ segredos: Segredo[] }>(gerencia ? "/segredos" : null, { enabled: gerencia });
  const [escolhido, setEscolhido] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const lista = Array.isArray(meus.data?.segredos) ? meus.data.segredos : [];
  const disponiveis = (Array.isArray(todos.data?.segredos) ? todos.data.segredos : []).filter((s) => !lista.some((m) => m.id === s.id));

  async function mudar(metodo: "POST" | "DELETE", segredoId: string, sucesso: string) {
    setOcupado(true);
    try {
      await apiRequest(`/segredos/da-automacao/${id}/${segredoId}`, { token, method: metodo });
      toast({ title: sucesso, kind: "success" });
      setEscolhido("");
      await Promise.all([meus.refetch(), todos.refetch()]);
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Bloco titulo="Segredos que usa" icone={<KeyRound className="h-5 w-5 text-primary" />} testid="tecnico-segredos"
      acao={<Link href="/secrets" className="text-sm font-medium text-primary hover:underline">Segredos</Link>}>
      {lista.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum segredo ligado. Senhas ligadas aqui chegam à automação por <code className="font-mono">a.segredo(&quot;chave&quot;)</code>.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {lista.map((s) => (
            <li key={s.id} className="flex items-center gap-2" data-segredo={s.chave}>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{s.nome}</p>
                <p className="truncate font-mono text-xs text-muted-foreground">{s.chave} · {s.ultimo_uso ? `usado ${relativo(s.ultimo_uso)}` : "ainda não usou"}</p>
              </div>
              {(s.situacao !== "active" || s.vencido) && <SituacaoDoSegredo situacao={s.situacao} vencido={s.vencido} />}
              {gerencia && (
                <button type="button" aria-label={`Desligar ${s.chave}`} title="Desligar desta automação" disabled={ocupado}
                  className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                  onClick={() => void mudar("DELETE", s.id, `${s.chave} desligado desta automação`)}>
                  <X className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {gerencia && disponiveis.length > 0 && (
        <div className="flex gap-2 border-t border-border pt-3">
          <Select aria-label="Segredo para ligar" value={escolhido} onChange={(e) => setEscolhido(e.target.value)} className="flex-1">
            <option value="">Ligar um segredo...</option>
            {disponiveis.map((s) => <option key={s.id} value={s.id}>{s.nome} ({s.chave})</option>)}
          </Select>
          <Button size="sm" disabled={!escolhido || ocupado} onClick={() => void mudar("POST", escolhido, "Segredo ligado à automação")}>Ligar</Button>
        </div>
      )}
    </Bloco>
  );
}
