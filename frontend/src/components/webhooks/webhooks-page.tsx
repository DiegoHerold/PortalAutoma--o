"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight, Check, CheckCircle2, Copy, Globe, KeyRound, Plus, RotateCcw, Search, ShieldCheck, Timer, Trash2, Webhook, XCircle,
} from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { PageTitle } from "@/components/shared/page-title";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Sheet } from "@/components/ui/sheet";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Campo, Formulario } from "@/lib/campos";
import { podeGerenciar } from "@/lib/permissions";
import { haQuanto } from "@/lib/tempo";
import { cn, formatDateTime } from "@/lib/utils";

/*
 * Webhooks (13/11/2026): uma URL para um sistema de fora ACIONAR uma automação. Só aciona; não lê
 * nada do Portal (para isso existe a conta de serviço). Token só no cabeçalho, mostrado uma vez;
 * IPs permitidos e limite por minuto opcionais; campos e itens conferidos pelo formulário da
 * automação, igual ao Executar. Cada chamada, aceita ou recusada, fica no histórico do webhook.
 *
 * Tela (13/11/2026, 2ª versão): cartões com o que importa para acompanhar (situação, chamadas das
 * últimas 24 h, último uso), um resumo no topo e o detalhe em abas: Chamadas, Como chamar, Proteção.
 */

export type WebhookResumo = {
  id: string; url: string; automacao: { id: number; nome: string | null }; nome: string; descricao: string | null; ativo: boolean;
  tem_token: boolean; token_final: string | null; token_criado_em: string | null; ips_permitidos: string[];
  limite_por_minuto: number; ultimo_uso_em: string | null; criado_em: string | null; migrado: boolean;
  chamadas_24h: { aceitas: number; recusadas: number };
};
type ChamadaRecebida = { id: string; recebida_em: string; situacao: "aceita" | "repetida" | "recusada"; motivo: string | null;
  codigo_http: number; ip: string | null; execucao_id: string | null; itens: number | null };
type Automacao = { id: number; name: string; status?: string; is_active?: boolean };
type Aba = "chamadas" | "chamar" | "protecao";

export { haQuanto };

export function SituacaoDoWebhook({ webhook }: { webhook: WebhookResumo }) {
  if (!webhook.tem_token) return <Badge tone="warning">Sem token</Badge>;
  return webhook.ativo ? <Badge tone="success">Ligado</Badge> : <Badge tone="neutral">Desligado</Badge>;
}

function Copiar({ texto, rotulo, comTexto = false }: { texto: string; rotulo: string; comTexto?: boolean }) {
  const [ok, setOk] = useState(false);
  return (
    <button type="button" aria-label={rotulo} title={rotulo}
      className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground",
        comTexto ? "border border-border px-2.5 py-1.5 text-sm" : "p-1.5")}
      onClick={() => { void navigator.clipboard.writeText(texto).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); }).catch(() => undefined); }}>
      {ok ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
      {comTexto && (ok ? "Copiado" : "Copiar")}
    </button>
  );
}

function valorDeExemplo(c: Campo): unknown {
  if (c.tipo === "mes_ano") return "10/2026";
  if (c.tipo === "sim_nao") return true;
  if (c.tipo === "numero" || c.tipo === "inteiro") return 1;
  if (c.tipo === "lista") return c.opcoes[0] ?? "";
  if (c.tipo === "data") return "2026-11-13";
  return "...";
}

function exemploDoCorpo(form: Formulario | null | undefined): string {
  const parametros: Record<string, unknown> = {};
  for (const c of form?.entrada ?? []) if (!c.fora_de_uso) parametros[c.chave] = valorDeExemplo(c);
  const corpo: Record<string, unknown> = { parametros };
  if (form?.item) corpo.itens = ["101", "102"];
  return JSON.stringify(corpo, null, 2);
}

function exemploCurl(url: string, token: string, corpo: string): string {
  return [`curl -X POST "${url}" \\`, `  -H "Authorization: Bearer ${token}" \\`, `  -H "Content-Type: application/json" \\`,
    `  -H "Idempotency-Key: pedido-123" \\`, `  -d '${corpo}'`].join("\n");
}

// -- página ---------------------------------------------------------------------------------------

export function WebhooksPage() {
  const { user } = useAuth();
  const gerencia = podeGerenciar(user, "webhooks");
  const webhooks = useApi<{ webhooks: WebhookResumo[] }>("/webhooks");
  const [busca, setBusca] = useState("");
  const [aberto, setAberto] = useState<string | null>(null);
  const [novo, setNovo] = useState(false);
  const [token, setToken] = useState<{ webhook: WebhookResumo; token: string } | null>(null);

  const lista = useMemo(() => (Array.isArray(webhooks.data?.webhooks) ? webhooks.data.webhooks : []), [webhooks.data]);
  const filtrada = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return termo ? lista.filter((w) => [w.nome, w.automacao.nome ?? ""].some((t) => t.toLowerCase().includes(termo))) : lista;
  }, [lista, busca]);
  const selecionado = lista.find((w) => w.id === aberto) ?? null;
  const resumo = useMemo(() => ({
    ligados: lista.filter((w) => w.ativo && w.tem_token).length,
    aceitas: lista.reduce((s, w) => s + w.chamadas_24h.aceitas, 0),
    recusadas: lista.reduce((s, w) => s + w.chamadas_24h.recusadas, 0),
    semToken: lista.filter((w) => !w.tem_token).length,
  }), [lista]);

  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Operação" title="Webhooks"
        description="Uma URL para um sistema de fora acionar uma automação. Só aciona: não lê nada do Portal." />

      {lista.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3" data-testid="resumo-dos-webhooks">
          <Numero rotulo="Ligados" valor={resumo.ligados} detalhe={`de ${lista.length}`}
            aviso={resumo.semToken ? `${resumo.semToken} sem token` : null} />
          <Numero rotulo="Aceitas nas últimas 24 h" valor={resumo.aceitas} tom="success" />
          <Numero rotulo="Recusadas nas últimas 24 h" valor={resumo.recusadas} tom={resumo.recusadas ? "destructive" : undefined} />
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar webhook ou automação..." value={busca} onChange={(e) => setBusca(e.target.value)} />
        </div>
        {gerencia && <Button onClick={() => setNovo(true)}><Plus className="h-4 w-4" /> Novo webhook</Button>}
      </div>

      {webhooks.error ? (
        <ErrorState message={webhooks.error} onRetry={webhooks.refetch} />
      ) : webhooks.loading && !webhooks.data ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-48 rounded-xl" />)}</div>
      ) : filtrada.length === 0 ? (
        <EmptyState icon={Webhook} title={lista.length ? "Nenhum webhook encontrado" : "Nenhum webhook"}
          description="Crie um quando um sistema de fora (ERP, Power Automate, script) precisar disparar uma automação."
          action={gerencia && !lista.length ? <Button onClick={() => setNovo(true)}><Plus className="h-4 w-4" /> Novo webhook</Button> : undefined} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="lista-de-webhooks">
          {filtrada.map((w) => <CartaoDoWebhook key={w.id} webhook={w} onAbrir={() => setAberto(w.id)} />)}
        </div>
      )}

      <NovoWebhook aberto={novo} onFechar={() => setNovo(false)}
        onCriado={async (r) => { setNovo(false); await webhooks.refetch(); setToken(r); }} />
      <DetalhesDoWebhook webhook={selecionado} gerencia={gerencia} onFechar={() => setAberto(null)} onMudou={webhooks.refetch}
        onToken={(r) => setToken(r)} />
      <TokenUmaVez dados={token} onFechar={() => { const id = token?.webhook.id; setToken(null); if (id) setAberto(id); }} />
    </div>
  );
}

function Numero({ rotulo, valor, detalhe, aviso, tom }: { rotulo: string; valor: number; detalhe?: string; aviso?: string | null;
  tom?: "success" | "destructive" }) {
  return (
    <div className="rounded-xl border border-border bg-card px-5 py-4 shadow-sm">
      <p className="text-sm text-muted-foreground">{rotulo}</p>
      <p className="mt-1 flex items-baseline gap-2">
        <span className={cn("text-3xl font-semibold tabular-nums text-titulo", tom === "success" && valor > 0 && "text-success",
          tom === "destructive" && "text-destructive")}>{valor}</span>
        {detalhe && <span className="text-sm text-muted-foreground">{detalhe}</span>}
        {aviso && <span className="ml-auto text-sm font-medium text-warning">{aviso}</span>}
      </p>
    </div>
  );
}

function CartaoDoWebhook({ webhook: w, onAbrir }: { webhook: WebhookResumo; onAbrir: () => void }) {
  const ligado = w.ativo && w.tem_token;
  return (
    <article data-webhook={w.nome}
      className={cn("group relative flex flex-col gap-4 rounded-xl border bg-card p-5 shadow-sm transition-colors hover:border-primary/40",
        !w.tem_token ? "border-warning/40" : "border-border")}>
      <button type="button" onClick={onAbrir} aria-label={w.nome} className="absolute inset-0 z-0 rounded-xl" />
      <div className="pointer-events-none relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-lg font-semibold leading-snug text-titulo group-hover:underline">
            <span className={cn("h-2 w-2 shrink-0 rounded-full", ligado ? "bg-success" : w.tem_token ? "bg-muted-foreground/50" : "bg-warning")} />
            <span className="truncate">{w.nome}</span>
          </h3>
          <p className="mt-0.5 flex items-center gap-1 truncate text-sm text-muted-foreground">
            <ArrowRight className="h-3.5 w-3.5 shrink-0" /> {w.automacao.nome ?? `automação ${w.automacao.id}`}
          </p>
        </div>
        <SituacaoDoWebhook webhook={w} />
      </div>

      {!w.tem_token ? (
        <p className="pointer-events-none relative rounded-lg bg-warning/10 px-3 py-2 text-sm text-warning">
          {w.migrado ? "Veio do webhook antigo: gere um token e ligue." : "Gere um token para ligar."}
        </p>
      ) : (
        <div className="pointer-events-none relative grid grid-cols-3 gap-2 rounded-lg bg-muted/40 px-3 py-2.5">
          <div>
            <p className="text-2xl font-semibold tabular-nums text-titulo">{w.chamadas_24h.aceitas}</p>
            <p className="text-xs text-muted-foreground">aceitas 24 h</p>
          </div>
          <div>
            <p className={cn("text-2xl font-semibold tabular-nums", w.chamadas_24h.recusadas ? "text-destructive" : "text-titulo")}>{w.chamadas_24h.recusadas}</p>
            <p className="text-xs text-muted-foreground">recusadas 24 h</p>
          </div>
          <div>
            <p className="pt-1 text-base font-medium text-titulo">{w.ultimo_uso_em ? haQuanto(w.ultimo_uso_em) : "nunca"}</p>
            <p className="text-xs text-muted-foreground">último uso</p>
          </div>
        </div>
      )}

      <div className="pointer-events-none relative mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><Globe className="h-3.5 w-3.5" />
          {w.ips_permitidos.length ? `${w.ips_permitidos.length} IP/rede` : "qualquer IP"}</span>
        <span className="flex items-center gap-1"><Timer className="h-3.5 w-3.5" /> {w.limite_por_minuto}/min</span>
        {w.tem_token && <span className="flex items-center gap-1 font-mono"><KeyRound className="h-3.5 w-3.5" /> …{w.token_final}</span>}
      </div>
    </article>
  );
}

// -- novo ----------------------------------------------------------------------------------------

function NovoWebhook({ aberto, onFechar, onCriado }: { aberto: boolean; onFechar: () => void;
  onCriado: (r: { webhook: WebhookResumo; token: string }) => Promise<void> }) {
  const { token } = useAuth();
  const automacoes = useApi<Automacao[]>(aberto ? "/automations" : null, { enabled: aberto });
  const vazio = { automacao: "", nome: "", descricao: "", ips: "", limite: "30" };
  const [f, setF] = useState(vazio);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const opcoes = (Array.isArray(automacoes.data) ? automacoes.data : []).filter((a) => a.status !== "archived" && a.is_active !== false);

  function fechar() { setF(vazio); setErro(null); onFechar(); }

  async function salvar() {
    if (!f.automacao || !f.nome.trim()) return setErro("Escolha a automação e dê um nome (quem vai chamar).");
    setSalvando(true); setErro(null);
    try {
      const r = await apiRequest<{ webhook: WebhookResumo; token: string }>("/webhooks", { token, method: "POST", body: JSON.stringify({
        automation_id: Number(f.automacao), nome: f.nome.trim(), descricao: f.descricao.trim() || null,
        ips_permitidos: f.ips, limite_por_minuto: Number(f.limite) || 30 }) });
      setF(vazio);
      await onCriado(r);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível criar o webhook.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open={aberto} onClose={fechar} title="Novo webhook" description="O token aparece uma única vez, logo depois de criar." className="max-w-xl"
      footer={<><Button variant="ghost" onClick={fechar}>Cancelar</Button><Button onClick={() => void salvar()} disabled={salvando}>{salvando ? "Criando..." : "Criar e mostrar o token"}</Button></>}>
      <div className="space-y-4">
        {erro && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{erro}</p>}
        <Field><Label htmlFor="webhook-automacao">Automação que ele aciona</Label>
          <Select id="webhook-automacao" value={f.automacao} onChange={(e) => setF({ ...f, automacao: e.target.value })}>
            <option value="">Escolha...</option>
            {opcoes.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </Select></Field>
        <Field><Label htmlFor="webhook-nome">Nome (quem vai chamar)</Label>
          <Input id="webhook-nome" value={f.nome} placeholder="ERP Protheus" onChange={(e) => setF({ ...f, nome: e.target.value })} /></Field>
        <Field><Label htmlFor="webhook-descricao">Para que serve <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Textarea id="webhook-descricao" rows={2} value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} /></Field>
        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <Field><Label htmlFor="webhook-ips">IPs permitidos <span className="font-normal text-muted-foreground">(opcional)</span></Label>
            <Input id="webhook-ips" value={f.ips} placeholder="10.0.8.15, 10.0.9.0/24" onChange={(e) => setF({ ...f, ips: e.target.value })} />
            <p className="text-xs text-muted-foreground">Vazio: aceita de qualquer IP (o token continua obrigatório).</p></Field>
          <Field><Label htmlFor="webhook-limite">Por minuto</Label>
            <Input id="webhook-limite" type="number" min={1} max={600} value={f.limite} onChange={(e) => setF({ ...f, limite: e.target.value })} /></Field>
        </div>
      </div>
    </Modal>
  );
}

// -- detalhe --------------------------------------------------------------------------------------

function DetalhesDoWebhook({ webhook, gerencia, onFechar, onMudou, onToken }: { webhook: WebhookResumo | null; gerencia: boolean;
  onFechar: () => void; onMudou: () => Promise<unknown>; onToken: (r: { webhook: WebhookResumo; token: string }) => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const chamadas = useApi<{ chamadas: ChamadaRecebida[] }>(webhook ? `/webhooks/${webhook.id}/chamadas?limite=50` : null, { enabled: !!webhook });
  const formulario = useApi<Formulario>(webhook ? `/automations/${webhook.automacao.id}/formulario` : null, { enabled: !!webhook });
  const [aba, setAba] = useState<Aba>("chamadas");
  const [ocupado, setOcupado] = useState(false);
  const [confirmar, setConfirmar] = useState<"token" | "apagar" | null>(null);
  const lista = Array.isArray(chamadas.data?.chamadas) ? chamadas.data.chamadas : [];

  // Sem chamadas ainda (ou sem token): o que importa é aprender a chamar.
  useEffect(() => {
    if (webhook) setAba(webhook.tem_token && (webhook.chamadas_24h.aceitas + webhook.chamadas_24h.recusadas > 0 || webhook.ultimo_uso_em) ? "chamadas" : "chamar");
  }, [webhook?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function enviar<T>(caminho: string, metodo: string, corpo: unknown, sucesso: string | null): Promise<T | null> {
    setOcupado(true);
    try {
      const r = await apiRequest<T>(caminho, { token, method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      if (sucesso) toast({ title: sucesso, kind: "success" });
      await onMudou();
      return r;
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return null;
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Sheet open={!!webhook} onClose={onFechar} widthClassName="w-full sm:max-w-3xl"
      title={webhook ? <span className="flex items-center gap-3">{webhook.nome} <SituacaoDoWebhook webhook={webhook} /></span> : undefined}
      description={webhook ? <>aciona <Link href={`/automations/${webhook.automacao.id}`} className="font-medium text-primary hover:underline">{webhook.automacao.nome}</Link>
        {webhook.descricao ? <> · {webhook.descricao}</> : null}</> : undefined}>
      {webhook && (
        <div className="space-y-5" data-testid="detalhes-do-webhook">
          {!webhook.tem_token && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/5 p-4">
              <p className="text-sm">{webhook.migrado
                ? "Veio do webhook antigo: o endereço e o token mudaram. Gere um token, ligue e atualize o sistema que chama."
                : "Gere um token para o webhook começar a aceitar chamadas."}</p>
              {gerencia && <Button size="sm" onClick={() => setConfirmar("token")}><KeyRound className="h-4 w-4" /> Gerar token</Button>}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={aba} onValueChange={(v) => setAba(v as Aba)} items={[
              { value: "chamadas", label: "Chamadas", count: lista.length || undefined },
              { value: "chamar", label: "Como chamar" },
              { value: "protecao", label: "Proteção" },
            ]} />
            {gerencia && webhook.tem_token && (
              <Button size="sm" variant={webhook.ativo ? "outline" : "primary"} disabled={ocupado}
                onClick={() => void enviar(`/webhooks/${webhook.id}`, "PUT", { ativo: !webhook.ativo }, webhook.ativo ? "Webhook desligado" : "Webhook ligado")}>
                {webhook.ativo ? "Desligar" : "Ligar"}
              </Button>
            )}
          </div>

          {aba === "chamadas" && <AbaChamadas lista={lista} carregando={chamadas.loading && !chamadas.data} />}
          {aba === "chamar" && <AbaComoChamar webhook={webhook} formulario={formulario.data} />}
          {aba === "protecao" && (
            <AbaProtecao webhook={webhook} gerencia={gerencia} ocupado={ocupado}
              salvar={(corpo) => void enviar(`/webhooks/${webhook.id}`, "PUT", corpo, "Proteção salva")}
              pedirToken={() => setConfirmar("token")} pedirApagar={() => setConfirmar("apagar")} />
          )}
        </div>
      )}

      <Modal open={confirmar === "token"} onClose={() => setConfirmar(null)} title={webhook?.tem_token ? "Gerar novo token" : "Gerar token"} description={webhook?.nome}
        footer={<><Button variant="ghost" onClick={() => setConfirmar(null)}>Cancelar</Button>
          <Button variant={webhook?.tem_token ? "destructive" : "primary"} disabled={ocupado} onClick={async () => {
            if (!webhook) return;
            const r = await enviar<{ webhook: WebhookResumo; token: string }>(`/webhooks/${webhook.id}/token`, "POST", undefined, null);
            setConfirmar(null);
            if (r) onToken(r);
          }}>Gerar</Button></>}>
        <p className="text-sm">{webhook?.tem_token
          ? <>O token atual (<span className="font-mono">wht_…{webhook.token_final}</span>) para de funcionar na hora. Atualize o sistema que chama logo em seguida.</>
          : "O token aparece uma única vez. Depois, ligue o webhook."}</p>
      </Modal>
      <Modal open={confirmar === "apagar"} onClose={() => setConfirmar(null)} title="Apagar webhook" description={webhook?.nome}
        footer={<><Button variant="ghost" onClick={() => setConfirmar(null)}>Cancelar</Button>
          <Button variant="destructive" disabled={ocupado} onClick={async () => {
            if (!webhook) return;
            const r = await enviar(`/webhooks/${webhook.id}`, "DELETE", undefined, "Webhook apagado");
            setConfirmar(null);
            if (r !== null) onFechar();
          }}>Apagar</Button></>}>
        <p className="text-sm">A URL para de responder e o histórico de chamadas sai junto. As execuções que ele pediu continuam no Histórico.
          Para só pausar, use Desligar.</p>
      </Modal>
    </Sheet>
  );
}

const ICONE = { aceita: CheckCircle2, repetida: RotateCcw, recusada: XCircle } as const;
const COR = { aceita: "text-success", repetida: "text-info", recusada: "text-destructive" } as const;

function AbaChamadas({ lista, carregando }: { lista: ChamadaRecebida[]; carregando: boolean }) {
  const [filtro, setFiltro] = useState<"todas" | "recusada">("todas");
  const vistas = filtro === "todas" ? lista : lista.filter((c) => c.situacao === "recusada");
  if (carregando) return <div className="skeleton h-48 rounded-lg" />;
  if (lista.length === 0) {
    return <p className="rounded-lg border border-dashed border-border p-6 text-center text-muted-foreground">Nenhuma chamada ainda.</p>;
  }
  const recusadas = lista.filter((c) => c.situacao === "recusada").length;
  return (
    <div className="space-y-3">
      {recusadas > 0 && (
        <div className="flex gap-2 text-sm">
          {(["todas", "recusada"] as const).map((f) => (
            <button key={f} type="button" onClick={() => setFiltro(f)}
              className={cn("rounded-full border px-3 py-1", filtro === f ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground")}>
              {f === "todas" ? `Todas (${lista.length})` : `Só recusadas (${recusadas})`}
            </button>
          ))}
        </div>
      )}
      <ul className="divide-y divide-border rounded-lg border border-border" data-testid="chamadas-do-webhook">
        {vistas.map((c) => {
          const Icone = ICONE[c.situacao];
          return (
            <li key={c.id} className="flex items-start gap-3 px-4 py-3" data-situacao={c.situacao}>
              <Icone className={cn("mt-0.5 h-5 w-5 shrink-0", COR[c.situacao])} />
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {c.situacao === "aceita" ? "Aceita" : c.situacao === "repetida" ? "Repetida (nada novo)" : "Recusada"}
                  {c.execucao_id && <> · <Link href={`/execucoes/${c.execucao_id}`} className="font-normal text-primary hover:underline">
                    ver execução{c.itens ? ` (${c.itens} ${c.itens === 1 ? "item" : "itens"})` : ""}</Link></>}
                </p>
                {c.situacao === "recusada" && c.motivo && <p className="text-sm text-muted-foreground">{c.motivo}</p>}
              </div>
              <div className="shrink-0 text-right text-sm">
                <p title={formatDateTime(c.recebida_em)}>{haQuanto(c.recebida_em)}</p>
                <p className="font-mono text-xs text-muted-foreground">{c.ip ?? ""} · {c.codigo_http}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const RESPOSTAS: [number, string][] = [
  [202, "Aceita: entrou na fila. Traz o execucao_id."],
  [200, "A Idempotency-Key já foi aceita nas últimas 24 h: nada novo foi criado."],
  [401, "Sem token ou token errado."],
  [403, "Webhook desligado, ou IP fora da lista."],
  [422, "Campos ou itens inválidos (o motivo vem em detalhe)."],
  [429, "Acima do limite de chamadas por minuto."],
];

function Passo({ numero, titulo, children }: { numero: number; titulo: string; children: React.ReactNode }) {
  return (
    <section className="flex gap-4">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{numero}</span>
      <div className="min-w-0 flex-1 space-y-2">
        <h3 className="font-semibold text-titulo">{titulo}</h3>
        {children}
      </div>
    </section>
  );
}

function AbaComoChamar({ webhook, formulario }: { webhook: WebhookResumo; formulario: Formulario | null | undefined }) {
  const corpo = exemploDoCorpo(formulario);
  const entrada = (formulario?.entrada ?? []).filter((c) => !c.fora_de_uso);
  return (
    <div className="space-y-6">
      <Passo numero={1} titulo="Endereço">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2">
          <Badge tone="primary">POST</Badge>
          <code className="min-w-0 flex-1 truncate font-mono text-sm" data-testid="url-do-webhook">{webhook.url}</code>
          <Copiar texto={webhook.url} rotulo="Copiar a URL" comTexto />
        </div>
      </Passo>

      <Passo numero={2} titulo="Cabeçalhos">
        <dl className="divide-y divide-border rounded-lg border border-border text-sm">
          <div className="flex gap-3 px-3 py-2"><dt className="w-40 shrink-0 font-mono">Authorization</dt>
            <dd>Bearer + o token {webhook.token_final ? <span className="font-mono text-muted-foreground">(wht_…{webhook.token_final})</span> : null}. Nunca na URL.</dd></div>
          <div className="flex gap-3 px-3 py-2"><dt className="w-40 shrink-0 font-mono">Content-Type</dt><dd>application/json</dd></div>
          <div className="flex gap-3 px-3 py-2"><dt className="w-40 shrink-0 font-mono">Idempotency-Key</dt>
            <dd>Opcional. A mesma chave em 24 h não cria outra execução.</dd></div>
        </dl>
      </Passo>

      <Passo numero={3} titulo="O que mandar">
        <ul className="divide-y divide-border rounded-lg border border-border text-sm" data-testid="campos-do-webhook">
          {entrada.map((c) => (
            <li key={c.chave} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
              <span className="font-mono">parametros.{c.chave}</span>
              <span className="text-muted-foreground">{c.rotulo}</span>
              {c.obrigatorio && c.padrao == null && <Badge tone="warning">obrigatório</Badge>}
            </li>
          ))}
          {formulario?.item && (
            <li className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
              <span className="font-mono">itens</span>
              <span className="text-muted-foreground">chaves de {formulario.item.nome.toLowerCase()}</span>
              <Badge tone="warning">obrigatório</Badge>
            </li>
          )}
          {!entrada.length && !formulario?.item && <li className="px-3 py-2 text-muted-foreground">Nada: a chamada só aciona.</li>}
        </ul>
        <p className="text-xs text-muted-foreground">Conferido como no botão Executar: campo desconhecido é recusado.</p>
      </Passo>

      <Passo numero={4} titulo="Exemplo">
        <div className="overflow-hidden rounded-lg border border-border">
          <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
            <span>curl</span>
            <Copiar texto={exemploCurl(webhook.url, "SEU_TOKEN", corpo)} rotulo="Copiar o exemplo" comTexto />
          </div>
          <pre className="overflow-x-auto bg-card p-4 font-mono text-xs leading-relaxed" data-testid="exemplo-do-webhook">{exemploCurl(webhook.url, "wht_…", corpo)}</pre>
        </div>
      </Passo>

      <Passo numero={5} titulo="Respostas">
        <ul className="divide-y divide-border rounded-lg border border-border text-sm">
          {RESPOSTAS.map(([codigo, texto]) => (
            <li key={codigo} className="flex gap-3 px-3 py-2">
              <span className={cn("w-10 shrink-0 font-mono font-semibold", codigo < 300 ? "text-success" : "text-destructive")}>{codigo}</span>
              <span>{texto}</span>
            </li>
          ))}
        </ul>
      </Passo>
    </div>
  );
}

function AbaProtecao({ webhook, gerencia, ocupado, salvar, pedirToken, pedirApagar }: { webhook: WebhookResumo; gerencia: boolean; ocupado: boolean;
  salvar: (corpo: Record<string, unknown>) => void; pedirToken: () => void; pedirApagar: () => void }) {
  const [ips, setIps] = useState(webhook.ips_permitidos.join("\n"));
  const [limite, setLimite] = useState(String(webhook.limite_por_minuto));
  useEffect(() => { setIps(webhook.ips_permitidos.join("\n")); setLimite(String(webhook.limite_por_minuto)); },
    [webhook.id, webhook.ips_permitidos.join(","), webhook.limite_por_minuto]); // eslint-disable-line react-hooks/exhaustive-deps
  const mudou = ips.trim() !== webhook.ips_permitidos.join("\n") || limite !== String(webhook.limite_por_minuto);

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border border-border p-4">
        <h3 className="flex items-center gap-2 font-semibold text-titulo"><KeyRound className="h-4 w-4 text-primary" /> Token</h3>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm">{webhook.tem_token
            ? <><span className="font-mono">wht_…{webhook.token_final}</span> <span className="text-muted-foreground">· gerado {haQuanto(webhook.token_criado_em)}</span></>
            : <span className="text-muted-foreground">Nenhum token ainda.</span>}</p>
          {gerencia && <Button size="sm" variant="outline" onClick={pedirToken}><KeyRound className="h-4 w-4" /> {webhook.tem_token ? "Novo token" : "Gerar token"}</Button>}
        </div>
        <p className="text-xs text-muted-foreground">O Portal guarda só uma impressão do token: ele não pode ser mostrado de novo. Novo token corta o atual na hora.</p>
      </section>

      <section className="space-y-3 rounded-lg border border-border p-4">
        <h3 className="flex items-center gap-2 font-semibold text-titulo"><ShieldCheck className="h-4 w-4 text-primary" /> De onde e quanto</h3>
        <div className="grid gap-4 sm:grid-cols-[1fr_9rem]">
          <Field><Label htmlFor="detalhe-ips">IPs permitidos</Label>
            <Textarea id="detalhe-ips" rows={3} value={ips} placeholder={"Vazio: qualquer IP\n10.0.8.15\n10.0.9.0/24"} disabled={!gerencia}
              className="font-mono text-sm" onChange={(e) => setIps(e.target.value)} />
            <p className="text-xs text-muted-foreground">Um por linha (IP ou rede). O token continua obrigatório.</p></Field>
          <Field><Label htmlFor="detalhe-limite">Por minuto</Label>
            <Input id="detalhe-limite" type="number" min={1} max={600} value={limite} disabled={!gerencia} onChange={(e) => setLimite(e.target.value)} />
            <p className="text-xs text-muted-foreground">Chamadas acima disso: 429.</p></Field>
        </div>
        {gerencia && (
          <div className="flex justify-end">
            <Button size="sm" disabled={!mudou || ocupado} onClick={() => salvar({ ips_permitidos: ips, limite_por_minuto: Number(limite) || 30 })}>
              Salvar proteção
            </Button>
          </div>
        )}
      </section>

      {gerencia && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 p-4">
          <div>
            <p className="font-semibold text-titulo">Apagar webhook</p>
            <p className="text-sm text-muted-foreground">A URL para de responder. Para só pausar, use Desligar.</p>
          </div>
          <Button size="sm" variant="destructive" onClick={pedirApagar}><Trash2 className="h-4 w-4" /> Apagar</Button>
        </section>
      )}
    </div>
  );
}

// -- token -----------------------------------------------------------------------------------------

function TokenUmaVez({ dados, onFechar }: { dados: { webhook: WebhookResumo; token: string } | null; onFechar: () => void }) {
  const [guardei, setGuardei] = useState(false);
  useEffect(() => { setGuardei(false); }, [dados?.token]);
  return (
    <Modal open={!!dados} onClose={() => guardei && onFechar()} title="Guarde o token agora" description={dados?.webhook.nome} className="max-w-2xl"
      footer={<Button onClick={onFechar} disabled={!guardei}>Fechar</Button>}>
      {dados && (
        <div className="space-y-4" data-testid="token-uma-vez">
          <p className="rounded-md border border-warning/30 bg-warning/5 p-3 text-sm">
            Ele não aparece de novo. Se perder, gere outro (o anterior para de funcionar). Vai sempre no cabeçalho, nunca na URL.
          </p>
          <div className="space-y-1">
            <p className="text-sm font-medium">Token</p>
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded-md bg-muted px-3 py-2 font-mono text-sm" data-testid="token">{dados.token}</code>
              <Copiar texto={dados.token} rotulo="Copiar o token" comTexto />
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">URL</p>
            <div className="flex items-center gap-2"><code className="min-w-0 flex-1 truncate rounded-md bg-muted px-3 py-2 font-mono text-xs">{dados.webhook.url}</code>
              <Copiar texto={dados.webhook.url} rotulo="Copiar a URL" comTexto /></div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4" checked={guardei} onChange={(e) => setGuardei(e.target.checked)} /> Guardei o token num lugar seguro
          </label>
        </div>
      )}
    </Modal>
  );
}
