"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Mail, Paperclip, Plus, RotateCw, Search, Send, X } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { PageTitle } from "@/components/shared/page-title";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { podeGerenciar } from "@/lib/permissions";
import { haQuanto } from "@/lib/tempo";
import { cn, formatDateTime } from "@/lib/utils";

/*
 * E-mails (13/11/2026): todo e-mail sai pelo Portal (Microsoft Graph). Aqui fica o que foi enviado
 * (das automações e do próprio Portal), o que a automação avisou que mandou pela máquina, o que
 * falhou ou foi recusado, e para quais domínios as automações podem mandar.
 */

type Situacao = "enviado" | "na_fila" | "falhou" | "recusado" | "enviado_pela_maquina";
type EmailResumo = {
  id: string; origem: "automacao" | "portal" | "maquina"; tipo: string; automacao: { id: number; nome: string | null } | null;
  execucao_id: string | null; para: string[]; cc: string[]; cco: string[]; assunto: string; situacao: Situacao; motivo: string | null;
  meio: string; tentativas: number; proxima_tentativa_em: string | null; criado_em: string; enviado_em: string | null;
  anexos: { nome: string; tamanho: number }[];
};
type Configuracao = { situacao: "ligado" | "desligado" | "incompleto"; remetente: string | null; dominio_do_remetente: string | null; dominios: string[] };

const SITUACAO: Record<Situacao, { texto: string; tom: "success" | "info" | "destructive" | "warning" | "neutral" }> = {
  enviado: { texto: "Enviado", tom: "success" },
  na_fila: { texto: "Na fila", tom: "info" },
  falhou: { texto: "Falhou", tom: "destructive" },
  recusado: { texto: "Recusado", tom: "warning" },
  enviado_pela_maquina: { texto: "Pela máquina", tom: "neutral" },
};
const FILTROS: { valor: string; rotulo: string }[] = [
  { valor: "", rotulo: "Todos" }, { valor: "falhou", rotulo: "Falharam" }, { valor: "na_fila", rotulo: "Na fila" },
  { valor: "recusado", rotulo: "Recusados" }, { valor: "enviado_pela_maquina", rotulo: "Pela máquina" },
];

function origemDe(e: EmailResumo): string {
  if (e.origem === "portal") return e.tipo === "notificacao" ? "Portal · notificação" : e.tipo === "teste" ? "Portal · teste" : "Portal";
  const nome = e.automacao?.nome ?? "automação";
  return e.origem === "maquina" ? `${nome} · pela máquina (${e.meio})` : nome;
}

function destinos(e: EmailResumo): string {
  const todos = [...e.para, ...e.cc];
  return todos.length > 2 ? `${todos.slice(0, 2).join(", ")} +${todos.length - 2}` : todos.join(", ");
}

export function EmailsPage() {
  const { user } = useAuth();
  const gerencia = podeGerenciar(user, "emails");
  const [aba, setAba] = useState<"emails" | "dominios">("emails");
  const [filtro, setFiltro] = useState("");
  const [busca, setBusca] = useState("");
  const [aberto, setAberto] = useState<string | null>(null);
  const consulta = new URLSearchParams({ limite: "100", ...(filtro ? { situacao: filtro } : {}), ...(busca.trim() ? { busca: busca.trim() } : {}) });
  const emails = useApi<{ emails: EmailResumo[]; resumo_24h: Record<string, number> }>(`/emails?${consulta.toString()}`);
  const config = useApi<Configuracao>("/emails/configuracao");
  const lista = useMemo(() => (Array.isArray(emails.data?.emails) ? emails.data.emails : []), [emails.data]);
  const resumo = emails.data?.resumo_24h ?? {};

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Governança" title="E-mails"
        description="Tudo o que o Portal enviou por e-mail, das automações e dele mesmo, e para onde as automações podem mandar." />

      <EstadoDoEnvio config={config.data} gerencia={gerencia} />

      <div className="grid gap-3 sm:grid-cols-4" data-testid="resumo-dos-emails">
        <Numero rotulo="Enviados (24 h)" valor={(resumo.enviado ?? 0) + (resumo.enviado_pela_maquina ?? 0)} tom="success" />
        <Numero rotulo="Na fila" valor={resumo.na_fila ?? 0} tom="info" />
        <Numero rotulo="Falharam" valor={resumo.falhou ?? 0} tom="destructive" />
        <Numero rotulo="Recusados" valor={resumo.recusado ?? 0} tom="warning" />
      </div>

      <Tabs value={aba} onValueChange={(v) => setAba(v as "emails" | "dominios")} items={[
        { value: "emails", label: "E-mails" }, { value: "dominios", label: "Destinos permitidos", count: config.data?.dominios.length },
      ]} />

      {aba === "dominios" ? <Dominios config={config.data} gerencia={gerencia} onMudou={config.refetch} /> : (
        <>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" placeholder="Buscar por assunto ou destinatário..." value={busca} onChange={(e) => setBusca(e.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              {FILTROS.map((f) => (
                <button key={f.valor} type="button" onClick={() => setFiltro(f.valor)}
                  className={cn("rounded-full border px-3 py-1 text-sm", filtro === f.valor ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                  {f.rotulo}
                </button>
              ))}
            </div>
          </div>
          {emails.error ? <ErrorState message={emails.error} onRetry={emails.refetch} /> : emails.loading && !emails.data ? (
            <div className="skeleton h-64 rounded-xl" />
          ) : lista.length === 0 ? (
            <EmptyState icon={Mail} title="Nenhum e-mail" description="Quando uma automação ou o Portal mandar um e-mail, ele aparece aqui." />
          ) : (
            <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-sm" data-testid="lista-de-emails">
              {lista.map((e) => (
                <li key={e.id} data-email={e.assunto}>
                  <button type="button" onClick={() => setAberto(e.id)} className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-muted/30">
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 truncate font-semibold text-titulo">
                        {e.assunto}{e.anexos.length > 0 && <Paperclip className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
                      </p>
                      <p className="truncate text-sm text-muted-foreground">para {destinos(e)} · {origemDe(e)}</p>
                      {(e.situacao === "falhou" || e.situacao === "recusado") && e.motivo && <p className="truncate text-sm text-destructive">{e.motivo}</p>}
                    </div>
                    <span className="hidden shrink-0 text-sm text-muted-foreground sm:block" title={formatDateTime(e.criado_em)}>{haQuanto(e.criado_em)}</span>
                    <Badge tone={SITUACAO[e.situacao]?.tom ?? "neutral"}>{SITUACAO[e.situacao]?.texto ?? e.situacao}</Badge>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <DetalheDoEmail id={aberto} gerencia={gerencia} onFechar={() => setAberto(null)} onMudou={emails.refetch} />
    </div>
  );
}

function Numero({ rotulo, valor, tom }: { rotulo: string; valor: number; tom: "success" | "info" | "destructive" | "warning" }) {
  const cor = { success: "text-success", info: "text-info", destructive: "text-destructive", warning: "text-warning" }[tom];
  return (
    <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <p className="text-sm text-muted-foreground">{rotulo}</p>
      <p className={cn("mt-1 text-3xl font-semibold tabular-nums", valor > 0 ? cor : "text-titulo")}>{valor}</p>
    </div>
  );
}

function EstadoDoEnvio({ config, gerencia }: { config: Configuracao | null | undefined; gerencia: boolean }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [enviando, setEnviando] = useState(false);
  if (!config) return null;
  const ligado = config.situacao === "ligado";
  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-3 rounded-xl border px-5 py-4",
      ligado ? "border-border bg-card" : "border-warning/40 bg-warning/5")} data-testid="estado-do-envio">
      <div className="flex items-center gap-3">
        <span className={cn("h-2.5 w-2.5 rounded-full", ligado ? "bg-success" : "bg-warning")} />
        <div>
          <p className="font-semibold text-titulo">{ligado ? "Envio ligado (Microsoft Graph)" : config.situacao === "incompleto" ? "Envio incompleto" : "Envio desligado"}</p>
          <p className="text-sm text-muted-foreground">
            {ligado ? <>Remetente <span className="font-medium text-foreground">{config.remetente}</span></>
              : "Os e-mails ficam na fila até o Graph estar configurado no .env do backend (ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, GRAPH_REMETENTE)."}
          </p>
        </div>
      </div>
      {gerencia && ligado && (
        <Button size="sm" variant="outline" disabled={enviando} onClick={async () => {
          setEnviando(true);
          try {
            const r = await apiRequest<{ situacao: string; motivo: string | null }>("/emails/teste", { token, method: "POST", body: "{}" });
            toast({ title: r.situacao === "enviado" ? "E-mail de teste enviado para você" : `E-mail de teste: ${r.situacao}`,
              description: r.motivo ?? undefined, kind: r.situacao === "enviado" ? "success" : "error" });
          } catch (err) {
            toast({ title: "Não foi possível mandar o teste", description: err instanceof Error ? err.message : undefined, kind: "error" });
          } finally {
            setEnviando(false);
          }
        }}><Send className="h-4 w-4" /> Mandar um teste para mim</Button>
      )}
    </div>
  );
}

function Dominios({ config, gerencia, onMudou }: { config: Configuracao | null | undefined; gerencia: boolean; onMudou: () => Promise<unknown> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [novo, setNovo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function mudar(caminho: string, metodo: string, corpo?: unknown) {
    setOcupado(true);
    try {
      await apiRequest(caminho, { token, method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      setNovo("");
      await onMudou();
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setOcupado(false);
    }
  }
  return (
    <div className="space-y-4" data-testid="dominios-permitidos">
      <p className="text-sm text-muted-foreground">
        As automações só mandam e-mail para o que está aqui: um domínio (libera o domínio inteiro e os subdomínios) ou um e-mail
        (libera só aquele endereço). Fora da lista, o pedido é recusado e fica registrado.
        Os e-mails do próprio Portal (notificações, login) não passam por esta lista.
      </p>
      <ul className="divide-y divide-border rounded-xl border border-border bg-card">
        {config?.dominio_do_remetente && (
          <li className="flex items-center justify-between px-4 py-3">
            <span className="font-mono">{config.dominio_do_remetente}</span>
            <span className="text-sm text-muted-foreground">domínio do remetente: sempre permitido (todos os @{config.dominio_do_remetente})</span>
          </li>
        )}
        {(config?.dominios ?? []).filter((d) => d !== config?.dominio_do_remetente).map((d) => (
          <li key={d} className="flex items-center justify-between px-4 py-3" data-dominio={d}>
            <span className="font-mono">{d}</span>
            {gerencia && (
              <button type="button" aria-label={`Tirar ${d}`} disabled={ocupado} onClick={() => void mudar(`/emails/dominios/${encodeURIComponent(d)}`, "DELETE")}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-destructive"><X className="h-4 w-4" /></button>
            )}
          </li>
        ))}
      </ul>
      {gerencia && (
        <form className="flex gap-2" onSubmit={(ev) => { ev.preventDefault(); if (novo.trim()) void mudar("/emails/dominios", "POST", { dominio: novo }); }}>
          <Input aria-label="Novo domínio" className="max-w-sm font-mono" placeholder="cliente.com.br ou joao@cliente.com.br" value={novo} onChange={(e) => setNovo(e.target.value)} />
          <Button type="submit" disabled={!novo.trim() || ocupado}><Plus className="h-4 w-4" /> Permitir</Button>
        </form>
      )}
    </div>
  );
}

function DetalheDoEmail({ id, gerencia, onFechar, onMudou }: { id: string | null; gerencia: boolean; onFechar: () => void; onMudou: () => Promise<unknown> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const dados = useApi<{ email: EmailResumo & { html: string | null; texto: string | null } }>(id ? `/emails/${id}` : null, { enabled: !!id });
  const e = dados.data?.email;
  const [ocupado, setOcupado] = useState(false);
  return (
    <Sheet open={!!id} onClose={onFechar} widthClassName="w-full sm:max-w-3xl" title={e?.assunto}
      description={e ? <span className="flex items-center gap-2"><Badge tone={SITUACAO[e.situacao]?.tom ?? "neutral"}>{SITUACAO[e.situacao]?.texto}</Badge>
        {formatDateTime(e.criado_em)}</span> : undefined}>
      {e && (
        <div className="space-y-5" data-testid="detalhe-do-email">
          {(e.situacao === "falhou" || e.situacao === "recusado" || e.situacao === "na_fila") && (
            <div className={cn("flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4 text-sm",
              e.situacao === "na_fila" ? "border-info/30 bg-info/5" : "border-destructive/30 bg-destructive/5")}>
              <p>{e.motivo ?? "Aguardando o envio."}{e.situacao === "na_fila" && e.proxima_tentativa_em ? ` Próxima tentativa ${formatDateTime(e.proxima_tentativa_em)}.` : ""}
                {e.tentativas > 0 ? ` (${e.tentativas} tentativa${e.tentativas > 1 ? "s" : ""})` : ""}</p>
              {gerencia && e.situacao === "falhou" && (
                <Button size="sm" variant="outline" disabled={ocupado} onClick={async () => {
                  setOcupado(true);
                  try {
                    const r = await apiRequest<{ situacao: string }>(`/emails/${e.id}/reenviar`, { token, method: "POST" });
                    toast({ title: r.situacao === "enviado" ? "Reenviado" : `Situação: ${r.situacao}`, kind: r.situacao === "enviado" ? "success" : "info" });
                    await Promise.all([dados.refetch(), onMudou()]);
                  } catch (err) {
                    toast({ title: "Não foi possível reenviar", description: err instanceof Error ? err.message : undefined, kind: "error" });
                  } finally {
                    setOcupado(false);
                  }
                }}><RotateCw className="h-4 w-4" /> Reenviar</Button>
              )}
            </div>
          )}
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[7rem_1fr]">
            <dt className="text-muted-foreground">Para</dt><dd>{e.para.join(", ")}</dd>
            {e.cc.length > 0 && <><dt className="text-muted-foreground">Cópia</dt><dd>{e.cc.join(", ")}</dd></>}
            {e.cco.length > 0 && <><dt className="text-muted-foreground">Cópia oculta</dt><dd>{e.cco.join(", ")}</dd></>}
            <dt className="text-muted-foreground">De onde</dt>
            <dd>{origemDe(e)}{e.execucao_id && <> · <Link href={`/execucoes/${e.execucao_id}`} className="text-primary hover:underline">ver execução</Link></>}</dd>
            {e.enviado_em && <><dt className="text-muted-foreground">Enviado</dt><dd>{formatDateTime(e.enviado_em)}</dd></>}
            {e.anexos.length > 0 && <><dt className="text-muted-foreground">Anexos</dt>
              <dd className="flex flex-wrap gap-2">{e.anexos.map((a) => <Badge key={a.nome} tone="outline"><Paperclip className="h-3 w-3" /> {a.nome}</Badge>)}</dd></>}
          </dl>
          <section className="space-y-2">
            <h3 className="font-semibold text-titulo">Mensagem</h3>
            {e.html ? (
              // Sem scripts nem formulários: o HTML só é mostrado.
              <iframe title="Mensagem" sandbox="" srcDoc={e.html} className="h-[28rem] w-full rounded-lg border border-border bg-white" data-testid="mensagem-html" />
            ) : (
              <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/30 p-4 text-sm">{e.texto ?? "—"}</pre>
            )}
          </section>
        </div>
      )}
    </Sheet>
  );
}
