"use client";

import { useMemo, useState } from "react";
import { KeyRound, Plus, RotateCw, Search } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Sheet } from "@/components/ui/sheet";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { relativo } from "@/lib/fila";
import { createSecret, rotateSecret } from "@/lib/governance-api";
import { podeGerenciar } from "@/lib/permissions";
import { formatDateTime } from "@/lib/utils";

/*
 * Segredos (13/11/2026): senhas e chaves que as automações recebem do Portal durante a execução.
 * A lista mostra o que importa: quais automações usam cada segredo, quando foi usado pela última
 * vez e se está ativo. O valor nunca volta do Portal; dá para trocar, não para ver.
 */

export type AutomacaoQueUsa = { id: number; nome: string; ligado_em: string | null; ultimo_uso: string | null };
export type Segredo = {
  id: string; chave: string; nome: string; descricao: string | null; situacao: "active" | "disabled" | string;
  versao: number | null; versao_criada_em: string | null; expira_em: string | null; vencido: boolean;
  atualizado_em: string | null; automacoes: AutomacaoQueUsa[]; ultimo_uso: string | null;
};
type Versao = { versao: number; criada_em: string | null; criada_por: string | null; expira_em: string | null; atual: boolean };
type Automacao = { id: number; name: string; status?: string };

export function SituacaoDoSegredo({ situacao, vencido }: { situacao: string; vencido: boolean }) {
  if (situacao !== "active") return <Badge tone="neutral">Desativado</Badge>;
  if (vencido) return <Badge tone="warning">Vencido</Badge>;
  return <Badge tone="success">Ativo</Badge>;
}

function chaveDe(texto: string) {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9._-]/g, "");
}

export function SecretsManager() {
  const { user } = useAuth();
  const gerencia = podeGerenciar(user, "segredos");
  const segredos = useApi<{ segredos: Segredo[] }>("/segredos");
  const [busca, setBusca] = useState("");
  const [aberto, setAberto] = useState<string | null>(null);
  const [novo, setNovo] = useState(false);

  const lista = useMemo(() => (Array.isArray(segredos.data?.segredos) ? segredos.data.segredos : []), [segredos.data]);
  const filtrada = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    if (!termo) return lista;
    return lista.filter((s) => [s.nome, s.chave, ...s.automacoes.map((a) => a.nome)].some((t) => t.toLowerCase().includes(termo)));
  }, [lista, busca]);
  const selecionado = lista.find((s) => s.id === aberto) ?? null;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar segredo ou automação..." value={busca} onChange={(e) => setBusca(e.target.value)} />
        </div>
        {gerencia && <Button onClick={() => setNovo(true)}><Plus className="h-4 w-4" /> Novo segredo</Button>}
      </div>

      {segredos.error ? (
        <ErrorState message={segredos.error} onRetry={segredos.refetch} />
      ) : segredos.loading && !segredos.data ? (
        <div className="skeleton h-64 rounded-xl" />
      ) : filtrada.length === 0 ? (
        <EmptyState icon={KeyRound} title={lista.length ? "Nenhum segredo encontrado" : "Nenhum segredo cadastrado"}
          description="Cadastre a senha uma vez aqui e ligue às automações que precisam dela, em vez de deixar no .env de cada máquina."
          action={gerencia && !lista.length ? <Button onClick={() => setNovo(true)}><Plus className="h-4 w-4" /> Novo segredo</Button> : undefined} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
          <table className="w-full min-w-[760px] text-sm" data-testid="lista-de-segredos">
            <thead className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr><th className="px-4 py-3">Segredo</th><th className="px-4 py-3">Usado por</th><th className="px-4 py-3">Último uso</th>
                <th className="px-4 py-3">Situação</th></tr>
            </thead>
            <tbody>
              {filtrada.map((s) => (
                <tr key={s.id} data-segredo={s.chave} className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/30"
                  onClick={() => setAberto(s.id)}>
                  <td className="px-4 py-3">
                    <button type="button" className="text-left font-semibold text-titulo hover:underline" onClick={() => setAberto(s.id)}>{s.nome}</button>
                    <p className="font-mono text-xs text-muted-foreground">{s.chave}{s.versao ? ` · versão ${s.versao}` : ""}</p>
                  </td>
                  <td className="px-4 py-3">
                    {s.automacoes.length === 0 ? <span className="text-muted-foreground">nenhuma automação</span> : (
                      <div className="flex flex-wrap gap-1">{s.automacoes.map((a) => <Badge key={a.id} tone="outline">{a.nome}</Badge>)}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{s.ultimo_uso ? relativo(s.ultimo_uso) : "nunca"}</td>
                  <td className="px-4 py-3"><SituacaoDoSegredo situacao={s.situacao} vencido={s.vencido} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NovoSegredo aberto={novo} onFechar={() => setNovo(false)} onCriado={async (id) => { setNovo(false); await segredos.refetch(); setAberto(id); }} />
      <DetalhesDoSegredo segredo={selecionado} gerencia={gerencia} onFechar={() => setAberto(null)} onMudou={segredos.refetch} />
    </div>
  );
}

function NovoSegredo({ aberto, onFechar, onCriado }: { aberto: boolean; onFechar: () => void; onCriado: (id: string) => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const vazio = { nome: "", chave: "", chaveMexida: false, descricao: "", valor: "", confirmar: "", expira: "" };
  const [f, setF] = useState(vazio);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  function fechar() { setF(vazio); setErro(null); onFechar(); }

  async function salvar() {
    if (!f.nome.trim() || !f.chave.trim() || !f.valor) return setErro("Preencha nome, chave e valor.");
    if (f.valor !== f.confirmar) return setErro("O valor e a confirmação não são iguais.");
    setSalvando(true); setErro(null);
    try {
      const r = await createSecret(token, { name: f.nome.trim(), key: f.chave.trim(), value: f.valor, description: f.descricao.trim() || undefined,
        expires_at: f.expira ? new Date(f.expira).toISOString() : undefined });
      toast({ title: "Segredo criado", description: "Agora ligue às automações que vão usá-lo.", kind: "success" });
      setF(vazio);
      await onCriado(r.secret.id);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível criar o segredo.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open={aberto} onClose={fechar} title="Novo segredo" description="O valor é guardado criptografado e nunca mais aparece no Portal."
      footer={<><Button variant="ghost" onClick={fechar}>Cancelar</Button><Button onClick={() => void salvar()} disabled={salvando}>{salvando ? "Salvando..." : "Criar segredo"}</Button></>}>
      <div className="space-y-4">
        {erro && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{erro}</p>}
        <Field><Label htmlFor="segredo-nome">Nome</Label>
          <Input id="segredo-nome" value={f.nome} placeholder="Senha do banco da Domínio"
            onChange={(e) => setF({ ...f, nome: e.target.value, chave: f.chaveMexida ? f.chave : chaveDe(e.target.value) })} /></Field>
        <Field><Label htmlFor="segredo-chave">Chave</Label>
          <Input id="segredo-chave" className="font-mono" value={f.chave} placeholder="dominio.senha_banco" autoComplete="off"
            onChange={(e) => setF({ ...f, chave: e.target.value, chaveMexida: true })} />
          <p className="text-xs text-muted-foreground">É o nome que a automação usa: <code className="font-mono">a.segredo(&quot;{f.chave || "dominio.senha_banco"}&quot;)</code></p></Field>
        <Field><Label htmlFor="segredo-descricao">Para que serve <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Textarea id="segredo-descricao" rows={2} value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field><Label htmlFor="segredo-valor">Valor</Label>
            <Input id="segredo-valor" type="password" autoComplete="new-password" value={f.valor} onChange={(e) => setF({ ...f, valor: e.target.value })} /></Field>
          <Field><Label htmlFor="segredo-confirmar">Confirmar valor</Label>
            <Input id="segredo-confirmar" type="password" autoComplete="new-password" value={f.confirmar} onChange={(e) => setF({ ...f, confirmar: e.target.value })} /></Field>
        </div>
        <Field><Label htmlFor="segredo-expira">Vence em <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Input id="segredo-expira" type="datetime-local" value={f.expira} onChange={(e) => setF({ ...f, expira: e.target.value })} /></Field>
      </div>
    </Modal>
  );
}

function DetalhesDoSegredo({ segredo, gerencia, onFechar, onMudou }: { segredo: Segredo | null; gerencia: boolean; onFechar: () => void; onMudou: () => Promise<unknown> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const versoes = useApi<{ versoes: Versao[] }>(segredo ? `/segredos/${segredo.id}/versoes` : null, { enabled: !!segredo });
  const automacoes = useApi<Automacao[]>(segredo && gerencia ? "/automations" : null, { enabled: !!segredo && gerencia });
  const [escolhidas, setEscolhidas] = useState<number[] | null>(null);
  const [trocando, setTrocando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  const ligadas = segredo?.automacoes.map((a) => a.id) ?? [];
  const marcadas = escolhidas ?? ligadas;
  const mudouLigacoes = escolhidas !== null && [...escolhidas].sort().join(",") !== [...ligadas].sort().join(",");

  async function enviar(caminho: string, metodo: string, corpo: unknown, sucesso: string) {
    setOcupado(true);
    try {
      await apiRequest(caminho, { token, method: metodo, body: JSON.stringify(corpo) });
      toast({ title: sucesso, kind: "success" });
      setEscolhidas(null);
      await Promise.all([onMudou(), versoes.refetch()]);
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setOcupado(false);
    }
  }

  function fechar() { setEscolhidas(null); onFechar(); }

  const todas = (Array.isArray(automacoes.data) ? automacoes.data : []).filter((a) => a.status !== "archived" || ligadas.includes(a.id));

  return (
    <Sheet open={!!segredo} onClose={fechar} title={segredo?.nome} description={segredo ? <span className="font-mono">{segredo.chave}</span> : undefined}
      widthClassName="w-full sm:max-w-2xl">
      {segredo && (
        <div className="space-y-6" data-testid="detalhes-do-segredo">
          <section className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <SituacaoDoSegredo situacao={segredo.situacao} vencido={segredo.vencido} />
              <span className="text-sm text-muted-foreground">
                versão {segredo.versao ?? "—"}{segredo.expira_em ? ` · vence ${formatDateTime(segredo.expira_em)}` : ""}
              </span>
            </div>
            {gerencia && (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setTrocando(true)}><RotateCw className="h-4 w-4" /> Trocar valor</Button>
                <Button size="sm" variant="outline" disabled={ocupado}
                  onClick={() => void enviar(`/segredos/${segredo.id}`, "PUT", { situacao: segredo.situacao === "active" ? "disabled" : "active" },
                    segredo.situacao === "active" ? "Segredo desativado: nenhuma automação recebe mais" : "Segredo reativado")}>
                  {segredo.situacao === "active" ? "Desativar" : "Reativar"}
                </Button>
              </div>
            )}
          </section>
          {segredo.descricao && <p className="text-sm text-muted-foreground">{segredo.descricao}</p>}

          <section className="space-y-3">
            <h3 className="font-semibold text-titulo">Automações que usam</h3>
            {!gerencia ? (
              segredo.automacoes.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma automação usa este segredo.</p> : (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {segredo.automacoes.map((a) => (
                    <li key={a.id} className="flex justify-between px-3 py-2 text-sm"><span>{a.nome}</span>
                      <span className="text-muted-foreground">{a.ultimo_uso ? `usado ${relativo(a.ultimo_uso)}` : "ainda não usou"}</span></li>
                  ))}
                </ul>
              )
            ) : (
              <>
                <ul className="max-h-72 divide-y divide-border overflow-y-auto rounded-lg border border-border" data-testid="automacoes-do-segredo">
                  {todas.map((a) => {
                    const uso = segredo.automacoes.find((x) => x.id === a.id)?.ultimo_uso;
                    return (
                      <li key={a.id}>
                        <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-muted/30">
                          <input type="checkbox" className="h-4 w-4" checked={marcadas.includes(a.id)}
                            onChange={(e) => setEscolhidas(e.target.checked ? [...marcadas, a.id] : marcadas.filter((x) => x !== a.id))} />
                          <span className="flex-1">{a.name}</span>
                          {uso && <span className="text-xs text-muted-foreground">usado {relativo(uso)}</span>}
                        </label>
                      </li>
                    );
                  })}
                  {todas.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">Nenhuma automação cadastrada.</li>}
                </ul>
                <div className="flex justify-end gap-2">
                  {mudouLigacoes && <Button size="sm" variant="ghost" onClick={() => setEscolhidas(null)}>Desfazer</Button>}
                  <Button size="sm" disabled={!mudouLigacoes || ocupado}
                    onClick={() => void enviar(`/segredos/${segredo.id}/automacoes`, "PUT", { automacoes: marcadas }, "Automações atualizadas")}>
                    Salvar automações
                  </Button>
                </div>
              </>
            )}
          </section>

          <section className="space-y-2 rounded-lg border border-border bg-muted/20 p-4 text-sm">
            <h3 className="font-semibold text-titulo">Como a automação usa</h3>
            <pre className="overflow-x-auto rounded-md bg-card p-3 font-mono text-xs">{`senha = a.segredo("${segredo.chave}")`}</pre>
            <p className="text-muted-foreground">
              Só durante a execução e só nas automações marcadas acima (SDK 0.5.0, modo direto). O valor vira *** no log.
            </p>
          </section>

          <section className="space-y-2">
            <h3 className="font-semibold text-titulo">Versões</h3>
            <ul className="divide-y divide-border rounded-lg border border-border text-sm">
              {(versoes.data?.versoes ?? []).map((v) => (
                <li key={v.versao} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                  <span className="font-medium">Versão {v.versao} {v.atual && <Badge tone="primary">em uso</Badge>}</span>
                  <span className="text-muted-foreground">{formatDateTime(v.criada_em)}{v.expira_em ? ` · vence ${formatDateTime(v.expira_em)}` : ""}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      <TrocarValor segredo={trocando ? segredo : null} onFechar={() => setTrocando(false)}
        onTrocado={async () => { setTrocando(false); await Promise.all([onMudou(), versoes.refetch()]); }} />
    </Sheet>
  );
}

function TrocarValor({ segredo, onFechar, onTrocado }: { segredo: Segredo | null; onFechar: () => void; onTrocado: () => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [valor, setValor] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [expira, setExpira] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  function fechar() { setValor(""); setConfirmar(""); setExpira(""); setErro(null); onFechar(); }

  async function salvar() {
    if (!segredo) return;
    if (!valor) return setErro("Digite o novo valor.");
    if (valor !== confirmar) return setErro("O valor e a confirmação não são iguais.");
    setSalvando(true); setErro(null);
    try {
      await rotateSecret(token, segredo.id, { value: valor, expires_at: expira ? new Date(expira).toISOString() : undefined });
      toast({ title: "Valor trocado", description: "As próximas execuções já recebem o novo.", kind: "success" });
      setValor(""); setConfirmar(""); setExpira("");
      await onTrocado();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível trocar o valor.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open={!!segredo} onClose={fechar} title="Trocar valor" description={segredo ? `${segredo.nome} (${segredo.chave})` : undefined}
      footer={<><Button variant="ghost" onClick={fechar}>Cancelar</Button><Button onClick={() => void salvar()} disabled={salvando}>{salvando ? "Salvando..." : "Trocar valor"}</Button></>}>
      <div className="space-y-4">
        <p className="rounded-md border border-warning/30 bg-warning/5 p-3 text-sm">
          O valor novo vale a partir do próximo pedido. Execuções que já pegaram o valor antigo seguem com ele.
        </p>
        {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
        <Field><Label htmlFor="troca-valor">Novo valor</Label>
          <Input id="troca-valor" type="password" autoComplete="new-password" value={valor} onChange={(e) => setValor(e.target.value)} /></Field>
        <Field><Label htmlFor="troca-confirmar">Confirmar novo valor</Label>
          <Input id="troca-confirmar" type="password" autoComplete="new-password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)} /></Field>
        <Field><Label htmlFor="troca-expira">Vence em <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Input id="troca-expira" type="datetime-local" value={expira} onChange={(e) => setExpira(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
