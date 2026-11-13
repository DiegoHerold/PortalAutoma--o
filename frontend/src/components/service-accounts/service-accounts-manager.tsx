"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Copy, IdCard, KeyRound, Pencil, Plus, Trash2 } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";
import { relativo } from "@/lib/fila";
import { podeGerenciar } from "@/lib/permissions";
import { formatDateTime } from "@/lib/utils";

/*
 * Contas de serviço (13/11/2026): um sistema (ERP, Power BI, script) que chama a API do Portal sem
 * ser uma pessoa. O acesso é igual ao de uma pessoa: o PAPEL diz quais áreas da API, os TIMES dizem
 * em quais automações. A credencial (psa_...) aparece uma única vez; gerar outra para a anterior.
 */

type Conta = {
  id: string; nome: string; descricao: string | null; situacao: "active" | "disabled"; vencida: boolean;
  papel: { id: number; nome: string; slug: string } | null; times: { id: number; nome: string }[];
  expira_em: string | null; ultimo_uso: string | null; criada_em: string | null;
  credencial_final: string | null; credencial_criada_em: string | null; tem_credencial: boolean; usuario_id: number | null;
};
type Papel = { id: number; name: string; slug: string };
type Time = { id: number; name: string; status: string };
type Formulario = { id: string | null; nome: string; descricao: string; papel_id: string; times: number[]; expira: string; ativa: boolean };

function Situacao({ conta }: { conta: Conta }) {
  if (conta.situacao !== "active") return <Badge tone="neutral">{conta.tem_credencial ? "Desativada" : "Sem credencial"}</Badge>;
  if (conta.vencida) return <Badge tone="warning">Vencida</Badge>;
  return <Badge tone="success">Ativa</Badge>;
}

function paraCampoDeData(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function ServiceAccountsManager() {
  const { token, user } = useAuth();
  const { toast } = useToast();
  const gerencia = podeGerenciar(user, "contas_de_servico");
  const contas = useApi<{ contas: Conta[] }>("/contas-de-servico");
  const papeis = useApi<Papel[]>(gerencia ? "/roles" : null, { enabled: gerencia });
  const times = useApi<Time[]>(gerencia ? "/teams" : null, { enabled: gerencia });
  const [form, setForm] = useState<Formulario | null>(null);
  const [credencial, setCredencial] = useState<{ conta: string; valor: string } | null>(null);
  const [trocar, setTrocar] = useState<Conta | null>(null);
  const [apagar, setApagar] = useState<Conta | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const lista = useMemo(() => (Array.isArray(contas.data?.contas) ? contas.data.contas : []), [contas.data]);
  const opcoesDePapel = (Array.isArray(papeis.data) ? papeis.data : []).filter((p) => p.slug !== "admin");

  async function enviar<T>(caminho: string, metodo: string, corpo?: unknown): Promise<T | null> {
    setOcupado(true);
    try {
      const r = await apiRequest<T>(caminho, { token, method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      await contas.refetch();
      return r;
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return null;
    } finally {
      setOcupado(false);
    }
  }

  async function salvar() {
    if (!form) return;
    if (!form.nome.trim() || !form.papel_id) {
      toast({ title: "Preencha o nome e o papel", kind: "error" });
      return;
    }
    const corpo = { nome: form.nome.trim(), descricao: form.descricao, papel_id: Number(form.papel_id), times: form.times,
      expira_em: form.expira ? new Date(form.expira).toISOString() : null };
    if (form.id) {
      const r = await enviar<{ conta: Conta }>(`/contas-de-servico/${form.id}`, "PUT", { ...corpo, situacao: form.ativa ? "active" : "disabled" });
      if (r) { toast({ title: "Conta atualizada", kind: "success" }); setForm(null); }
    } else {
      const r = await enviar<{ conta: Conta; credencial: string }>("/contas-de-servico", "POST", corpo);
      if (r) { setForm(null); setCredencial({ conta: r.conta.nome, valor: r.credencial }); }
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 text-sm shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-muted-foreground">
          Para um <strong className="text-foreground">sistema</strong> que chama a API do Portal (ERP, Power BI, script). O acesso é
          igual ao de uma pessoa: o <strong className="text-foreground">papel</strong> diz quais áreas e os <strong className="text-foreground">times</strong> dizem
          em quais automações. Para disparar uma automação de fora, um webhook já basta.
        </p>
        {gerencia && (
          <Button className="shrink-0" onClick={() => setForm({ id: null, nome: "", descricao: "", papel_id: "", times: [], expira: "", ativa: true })}>
            <Plus className="h-4 w-4" /> Nova conta
          </Button>
        )}
      </div>

      {contas.error ? (
        <ErrorState message={contas.error} onRetry={contas.refetch} />
      ) : contas.loading && !contas.data ? (
        <div className="skeleton h-48 rounded-xl" />
      ) : lista.length === 0 ? (
        <EmptyState icon={IdCard} title="Nenhuma conta de serviço" description="Crie uma quando um sistema precisar falar com o Portal." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
          <table className="w-full min-w-[860px] text-sm" data-testid="lista-de-contas">
            <thead className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr><th className="px-4 py-3">Conta</th><th className="px-4 py-3">Papel</th><th className="px-4 py-3">Times</th>
                <th className="px-4 py-3">Credencial</th><th className="px-4 py-3">Último uso</th><th className="px-4 py-3">Situação</th>
                {gerencia && <th className="px-4 py-3" />}</tr>
            </thead>
            <tbody>
              {lista.map((c) => (
                <tr key={c.id} data-conta={c.nome} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-titulo">{c.nome}</p>
                    {c.descricao && <p className="line-clamp-1 text-xs text-muted-foreground">{c.descricao}</p>}
                  </td>
                  <td className="px-4 py-3">{c.papel ? <Badge tone="primary">{c.papel.nome}</Badge> : "—"}</td>
                  <td className="px-4 py-3">
                    {c.times.length === 0 ? <span className="text-muted-foreground">nenhum</span> : (
                      <div className="flex flex-wrap gap-1">{c.times.map((t) => <Badge key={t.id} tone="outline">{t.nome}</Badge>)}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {c.tem_credencial ? <><span className="font-mono">psa_…{c.credencial_final}</span><br /><span className="text-xs">gerada {relativo(c.credencial_criada_em)}</span></> : "nenhuma"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {c.ultimo_uso ? relativo(c.ultimo_uso) : "nunca"}
                    {c.expira_em && <span className="block text-xs">vence {formatDateTime(c.expira_em)}</span>}
                  </td>
                  <td className="px-4 py-3"><Situacao conta={c} /></td>
                  {gerencia && (
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button type="button" aria-label={`Editar ${c.nome}`} title="Editar" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                          onClick={() => setForm({ id: c.id, nome: c.nome, descricao: c.descricao ?? "", papel_id: c.papel ? String(c.papel.id) : "",
                            times: c.times.map((t) => t.id), expira: paraCampoDeData(c.expira_em), ativa: c.situacao === "active" })}>
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button type="button" aria-label={`Nova credencial para ${c.nome}`} title="Gerar nova credencial"
                          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" onClick={() => setTrocar(c)}>
                          <KeyRound className="h-4 w-4" />
                        </button>
                        <button type="button" aria-label={`Apagar ${c.nome}`} title="Apagar" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-destructive"
                          onClick={() => setApagar(c)}>
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Editar conta de serviço" : "Nova conta de serviço"}
        description={form?.id ? "Mudar a conta não troca a credencial." : "A credencial aparece uma única vez, logo depois de criar."} className="max-w-2xl"
        footer={<><Button variant="ghost" onClick={() => setForm(null)}>Cancelar</Button>
          <Button onClick={() => void salvar()} disabled={ocupado}>{ocupado ? "Salvando..." : form?.id ? "Salvar" : "Criar e mostrar a credencial"}</Button></>}>
        {form && (
          <div className="space-y-4">
            <Field><Label htmlFor="conta-nome">Nome (o sistema que vai usar)</Label>
              <Input id="conta-nome" value={form.nome} placeholder="ERP Protheus" onChange={(e) => setForm({ ...form, nome: e.target.value })} /></Field>
            <Field><Label htmlFor="conta-descricao">Para que serve <span className="font-normal text-muted-foreground">(opcional)</span></Label>
              <Textarea id="conta-descricao" rows={2} value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} /></Field>
            <Field><Label htmlFor="conta-papel">Papel <span className="font-normal text-muted-foreground">— quais áreas da API</span></Label>
              <Select id="conta-papel" value={form.papel_id} onChange={(e) => setForm({ ...form, papel_id: e.target.value })}>
                <option value="">Escolha o papel...</option>
                {opcoesDePapel.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Select>
              <p className="text-xs text-muted-foreground">Administrador não pode. Se nenhum serve, crie em Papéis um só com o que o sistema precisa.</p></Field>
            <div className="space-y-2">
              <Label>Times <span className="font-normal text-muted-foreground">— em quais automações</span></Label>
              {times.error ? <p className="text-sm text-muted-foreground">Só quem vê Times escolhe os times da conta.</p> : (
                <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                  {(Array.isArray(times.data) ? times.data : []).map((t) => (
                    <label key={t.id} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted/30">
                      <input type="checkbox" className="h-4 w-4" checked={form.times.includes(t.id)}
                        onChange={(e) => setForm({ ...form, times: e.target.checked ? [...form.times, t.id] : form.times.filter((x) => x !== t.id) })} />
                      {t.name}{t.status !== "active" && <Badge tone="neutral">inativo</Badge>}
                    </label>
                  ))}
                  {Array.isArray(times.data) && times.data.length === 0 && <p className="px-2 text-sm text-muted-foreground">Nenhum time cadastrado.</p>}
                </div>
              )}
            </div>
            <Field><Label htmlFor="conta-expira">Vence em <span className="font-normal text-muted-foreground">(opcional)</span></Label>
              <Input id="conta-expira" type="datetime-local" value={form.expira} onChange={(e) => setForm({ ...form, expira: e.target.value })} /></Field>
            {form.id && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4" checked={form.ativa} onChange={(e) => setForm({ ...form, ativa: e.target.checked })} />
                Conta ativa (desmarque para cortar o acesso sem apagar)
              </label>
            )}
          </div>
        )}
      </Modal>

      <Modal open={!!trocar} onClose={() => setTrocar(null)} title="Gerar nova credencial" description={trocar?.nome}
        footer={<><Button variant="ghost" onClick={() => setTrocar(null)}>Cancelar</Button>
          <Button variant="destructive" disabled={ocupado} onClick={async () => {
            if (!trocar) return;
            const r = await enviar<{ conta: Conta; credencial: string }>(`/contas-de-servico/${trocar.id}/credencial`, "POST");
            if (r) { setTrocar(null); setCredencial({ conta: r.conta.nome, valor: r.credencial }); }
          }}>Gerar nova</Button></>}>
        <p className="text-sm">A credencial atual {trocar?.tem_credencial ? <span className="font-mono">psa_…{trocar.credencial_final}</span> : null} para de funcionar na hora.
          Atualize o sistema que usa esta conta logo em seguida.</p>
      </Modal>

      <Modal open={!!apagar} onClose={() => setApagar(null)} title="Apagar conta de serviço" description={apagar?.nome}
        footer={<><Button variant="ghost" onClick={() => setApagar(null)}>Cancelar</Button>
          <Button variant="destructive" disabled={ocupado} onClick={async () => {
            if (!apagar) return;
            const ok = await enviar(`/contas-de-servico/${apagar.id}`, "DELETE");
            if (ok !== null) { toast({ title: "Conta apagada", kind: "success" }); setApagar(null); }
          }}>Apagar</Button></>}>
        <p className="text-sm">A credencial para de funcionar e a conta sai dos times. O que ela fez continua na auditoria.
          Para só cortar o acesso, edite e desmarque &quot;Conta ativa&quot;.</p>
      </Modal>

      <CredencialUmaVez credencial={credencial} onFechar={() => setCredencial(null)} />
    </div>
  );
}

function CredencialUmaVez({ credencial, onFechar }: { credencial: { conta: string; valor: string } | null; onFechar: () => void }) {
  const [copiado, setCopiado] = useState(false);
  const [guardei, setGuardei] = useState(false);
  useEffect(() => { setCopiado(false); setGuardei(false); }, [credencial?.valor]);
  const exemplo = `curl -H "Authorization: Bearer ${credencial?.valor ?? "psa_..."}" ${API_BASE_URL}/auth/me`;

  return (
    <Modal open={!!credencial} onClose={() => guardei && onFechar()} title="Guarde a credencial agora" description={credencial?.conta} className="max-w-2xl"
      footer={<Button onClick={onFechar} disabled={!guardei}>Fechar</Button>}>
      {credencial && (
        <div className="space-y-4" data-testid="credencial-uma-vez">
          <p className="rounded-md border border-warning/30 bg-warning/5 p-3 text-sm">
            Ela não aparece de novo. Se perder, gere outra (a anterior para de funcionar).
          </p>
          <div className="flex items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded-md bg-muted px-3 py-2 font-mono text-sm" data-testid="credencial">{credencial.valor}</code>
            <Button variant="outline" size="sm" onClick={() => { void navigator.clipboard.writeText(credencial.valor).then(() => setCopiado(true)).catch(() => undefined); }}>
              {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} {copiado ? "Copiada" : "Copiar"}
            </Button>
          </div>
          <div className="space-y-1 text-sm">
            <p className="font-medium">Como usar</p>
            <p className="text-muted-foreground">Sempre no cabeçalho <code className="font-mono">Authorization: Bearer</code>, nunca na URL. Para testar:</p>
            <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">{exemplo}</pre>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4" checked={guardei} onChange={(e) => setGuardei(e.target.checked)} /> Guardei a credencial num lugar seguro
          </label>
        </div>
      )}
    </Modal>
  );
}
