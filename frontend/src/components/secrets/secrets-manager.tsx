"use client";

import { useMemo, useState } from "react";
import { Eye, EyeOff, KeyRound, Pencil, Plus, Search, X } from "lucide-react";

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
import { podeGerenciar } from "@/lib/permissions";
import { formatDateTime } from "@/lib/utils";

/*
 * Segredos (13/11/2026): acessos que as automações recebem do Portal durante a execução. Um segredo
 * junta os campos de um acesso (Domínio: usuário, senha e banco). Campo OCULTO nunca aparece no
 * Portal e vira *** no log; campo VISÍVEL (usuário, banco) aparece e não é mascarado. A lista mostra
 * quais automações usam cada segredo, o último uso e se está ativo.
 */

export type AutomacaoQueUsa = { id: number; nome: string; ligado_em: string | null; ultimo_uso: string | null };
export type CampoDoSegredo = { nome: string; oculto: boolean; valor: string | null };
export type Segredo = {
  id: string; chave: string; nome: string; descricao: string | null; situacao: "active" | "disabled" | string;
  campos: CampoDoSegredo[]; versao: number | null; versao_criada_em: string | null; expira_em: string | null; vencido: boolean;
  atualizado_em: string | null; automacoes: AutomacaoQueUsa[]; ultimo_uso: string | null;
};
type Versao = { versao: number; criada_em: string | null; criada_por: string | null; expira_em: string | null; atual: boolean };
type Automacao = { id: number; name: string; status?: string };
type Linha = { nome: string; oculto: boolean; valor: string; existente: boolean };

const MODELOS: { rotulo: string; campos: Omit<Linha, "existente">[] }[] = [
  { rotulo: "Senha", campos: [{ nome: "senha", oculto: true, valor: "" }] },
  { rotulo: "Usuário e senha", campos: [{ nome: "usuario", oculto: false, valor: "" }, { nome: "senha", oculto: true, valor: "" }] },
  { rotulo: "Usuário, senha e banco", campos: [{ nome: "usuario", oculto: false, valor: "" }, { nome: "senha", oculto: true, valor: "" },
    { nome: "banco", oculto: false, valor: "" }] },
  { rotulo: "Token de API", campos: [{ nome: "token", oculto: true, valor: "" }] },
];

export function SituacaoDoSegredo({ situacao, vencido }: { situacao: string; vencido: boolean }) {
  if (situacao !== "active") return <Badge tone="neutral">Desativado</Badge>;
  if (vencido) return <Badge tone="warning">Vencido</Badge>;
  return <Badge tone="success">Ativo</Badge>;
}

function chaveDe(texto: string) {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9._-]/g, "");
}

function nomeDeCampo(texto: string) {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
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
          description="Cadastre o acesso uma vez aqui (usuário, senha, banco...) e ligue às automações que precisam dele, em vez de deixar no .env de cada máquina."
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
                    <p className="text-xs text-muted-foreground"><span className="font-mono">{s.chave}</span> · {(s.campos ?? []).map((c) => c.nome).join(", ")}</p>
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

/** Lista editável de campos: nome, valor e oculto/visível. Campo existente com valor vazio mantém o atual. */
function EditorDeCampos({ linhas, onMudar }: { linhas: Linha[]; onMudar: (linhas: Linha[]) => void }) {
  const mudar = (i: number, parte: Partial<Linha>) => onMudar(linhas.map((l, j) => (j === i ? { ...l, ...parte } : l)));
  return (
    <div className="space-y-2" data-testid="editor-de-campos">
      <div className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto_auto] gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <span>Campo</span><span>Valor</span><span>Oculto</span><span />
      </div>
      {linhas.map((l, i) => (
        <div key={i} className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto_auto] items-center gap-2" data-campo={l.nome || `novo-${i}`}>
          <Input aria-label={`Nome do campo ${i + 1}`} className="font-mono" value={l.nome} placeholder="senha" disabled={l.existente}
            onChange={(e) => mudar(i, { nome: nomeDeCampo(e.target.value) })} />
          <Input aria-label={`Valor de ${l.nome || `campo ${i + 1}`}`} type={l.oculto ? "password" : "text"} autoComplete="new-password"
            value={l.valor} placeholder={l.existente ? (l.oculto ? "manter o atual" : "") : ""} onChange={(e) => mudar(i, { valor: e.target.value })} />
          <button type="button" aria-label={l.oculto ? `${l.nome || "campo"} oculto` : `${l.nome || "campo"} visível`}
            title={l.oculto ? "Oculto: nunca aparece e vira *** no log" : "Visível: aparece no Portal"}
            className={`flex h-9 w-9 items-center justify-center rounded-md border ${l.oculto ? "border-primary/40 bg-primary/10 text-primary" : "border-border text-muted-foreground"}`}
            onClick={() => mudar(i, { oculto: !l.oculto })}>
            {l.oculto ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
          <button type="button" aria-label={`Tirar ${l.nome || `campo ${i + 1}`}`} disabled={linhas.length === 1}
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-destructive disabled:opacity-30"
            onClick={() => onMudar(linhas.filter((_, j) => j !== i))}>
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
      <Button type="button" size="sm" variant="ghost" onClick={() => onMudar([...linhas, { nome: "", oculto: true, valor: "", existente: false }])}>
        <Plus className="h-4 w-4" /> Adicionar campo
      </Button>
      <p className="text-xs text-muted-foreground"><EyeOff className="mr-1 inline h-3 w-3" />Oculto: nunca aparece e vira *** no log (senhas, tokens).
        <Eye className="ml-2 mr-1 inline h-3 w-3" />Visível: aparece aqui (usuário, banco, servidor).</p>
    </div>
  );
}

function validarLinhas(linhas: Linha[]): string | null {
  const nomes = linhas.map((l) => l.nome);
  if (nomes.some((n) => !/^[a-z][a-z0-9_]{0,39}$/.test(n))) return "Cada campo precisa de um nome (letras minúsculas, números e _).";
  if (new Set(nomes).size !== nomes.length) return "Há campos com o mesmo nome.";
  if (linhas.some((l) => !l.existente && !l.valor)) return "Preencha o valor dos campos novos.";
  return null;
}

function NovoSegredo({ aberto, onFechar, onCriado }: { aberto: boolean; onFechar: () => void; onCriado: (id: string) => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const vazio = { nome: "", chave: "", chaveMexida: false, descricao: "", expira: "" };
  const [f, setF] = useState(vazio);
  const [linhas, setLinhas] = useState<Linha[]>(MODELOS[0].campos.map((c) => ({ ...c, existente: false })));
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  function fechar() { setF(vazio); setLinhas(MODELOS[0].campos.map((c) => ({ ...c, existente: false }))); setErro(null); onFechar(); }

  async function salvar() {
    if (!f.nome.trim() || !f.chave.trim()) return setErro("Preencha nome e chave.");
    const problema = validarLinhas(linhas);
    if (problema) return setErro(problema);
    setSalvando(true); setErro(null);
    try {
      const r = await apiRequest<{ id: string }>("/segredos", { token, method: "POST", body: JSON.stringify({
        nome: f.nome.trim(), chave: f.chave.trim(), descricao: f.descricao.trim() || null,
        expira_em: f.expira ? new Date(f.expira).toISOString() : null,
        campos: linhas.map(({ nome, oculto, valor }) => ({ nome, oculto, valor })) }) });
      toast({ title: "Segredo criado", description: "Agora ligue às automações que vão usá-lo.", kind: "success" });
      fechar();
      await onCriado(r.id);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível criar o segredo.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open={aberto} onClose={fechar} title="Novo segredo" className="max-w-2xl"
      description="Os valores ficam guardados criptografados. Campos ocultos nunca mais aparecem no Portal."
      footer={<><Button variant="ghost" onClick={fechar}>Cancelar</Button><Button onClick={() => void salvar()} disabled={salvando}>{salvando ? "Salvando..." : "Criar segredo"}</Button></>}>
      <div className="space-y-4">
        {erro && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{erro}</p>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field><Label htmlFor="segredo-nome">Nome</Label>
            <Input id="segredo-nome" value={f.nome} placeholder="Acesso à Domínio"
              onChange={(e) => setF({ ...f, nome: e.target.value, chave: f.chaveMexida ? f.chave : chaveDe(e.target.value) })} /></Field>
          <Field><Label htmlFor="segredo-chave">Chave</Label>
            <Input id="segredo-chave" className="font-mono" value={f.chave} placeholder="dominio" autoComplete="off"
              onChange={(e) => setF({ ...f, chave: e.target.value, chaveMexida: true })} /></Field>
        </div>
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">Campos</span>
            <span className="text-muted-foreground">comece por:</span>
            {MODELOS.map((m) => (
              <button key={m.rotulo} type="button" className="rounded-full border border-border px-2.5 py-0.5 text-xs hover:border-primary hover:text-primary"
                onClick={() => setLinhas(m.campos.map((c) => ({ ...c, existente: false })))}>{m.rotulo}</button>
            ))}
          </div>
          <EditorDeCampos linhas={linhas} onMudar={setLinhas} />
        </div>
        <Field><Label htmlFor="segredo-descricao">Para que serve <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Textarea id="segredo-descricao" rows={2} value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} /></Field>
        <Field><Label htmlFor="segredo-expira">Vence em <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Input id="segredo-expira" type="datetime-local" value={f.expira} onChange={(e) => setF({ ...f, expira: e.target.value })} /></Field>
        <p className="rounded-md bg-muted/40 p-3 font-mono text-xs">{`acesso = a.segredo("${f.chave || "dominio"}")   # acesso["${linhas[0]?.nome || "senha"}"]`}</p>
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
  const [editando, setEditando] = useState(false);
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
  const campos = segredo?.campos ?? [];

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
              <Button size="sm" variant="outline" disabled={ocupado}
                onClick={() => void enviar(`/segredos/${segredo.id}`, "PUT", { situacao: segredo.situacao === "active" ? "disabled" : "active" },
                  segredo.situacao === "active" ? "Segredo desativado: nenhuma automação recebe mais" : "Segredo reativado")}>
                {segredo.situacao === "active" ? "Desativar" : "Reativar"}
              </Button>
            )}
          </section>
          {segredo.descricao && <p className="text-sm text-muted-foreground">{segredo.descricao}</p>}

          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-titulo">Campos</h3>
              {gerencia && <Button size="sm" variant="outline" onClick={() => setEditando(true)}><Pencil className="h-4 w-4" /> Editar campos</Button>}
            </div>
            <ul className="divide-y divide-border rounded-lg border border-border text-sm" data-testid="campos-do-segredo">
              {campos.map((c) => (
                <li key={c.nome} className="flex items-center gap-3 px-3 py-2" data-campo={c.nome}>
                  <span className="w-32 shrink-0 font-mono">{c.nome}</span>
                  <span className="min-w-0 flex-1 truncate">{c.oculto ? <span className="tracking-widest text-muted-foreground">••••••••</span> : c.valor ?? "—"}</span>
                  {c.oculto ? <Badge tone="primary"><EyeOff className="h-3 w-3" /> oculto</Badge> : <Badge tone="outline"><Eye className="h-3 w-3" /> visível</Badge>}
                </li>
              ))}
            </ul>
          </section>

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
            <pre className="overflow-x-auto rounded-md bg-card p-3 font-mono text-xs">{[`acesso = a.segredo("${segredo.chave}")`,
              ...campos.map((c) => `acesso["${c.nome}"]`)].join("\n")}</pre>
            <p className="text-muted-foreground">
              Só durante a execução e só nas automações marcadas acima (SDK 0.5.0, modo direto). Campos ocultos viram *** no log.
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
      <EditarCampos segredo={editando ? segredo : null} onFechar={() => setEditando(false)}
        onSalvo={async () => { setEditando(false); await Promise.all([onMudou(), versoes.refetch()]); }} />
    </Sheet>
  );
}

function EditarCampos({ segredo, onFechar, onSalvo }: { segredo: Segredo | null; onFechar: () => void; onSalvo: () => Promise<void> }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [expira, setExpira] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const atuais = linhas ?? (segredo?.campos ?? []).map((c) => ({ nome: c.nome, oculto: c.oculto, valor: c.oculto ? "" : c.valor ?? "", existente: true }));

  function fechar() { setLinhas(null); setExpira(null); setErro(null); onFechar(); }

  async function salvar() {
    if (!segredo) return;
    const problema = validarLinhas(atuais);
    if (problema) return setErro(problema);
    setSalvando(true); setErro(null);
    try {
      const corpo: Record<string, unknown> = { campos: atuais.map(({ nome, oculto, valor }) => ({ nome, oculto, valor })) };
      if (expira !== null) corpo.expira_em = expira ? new Date(expira).toISOString() : null;
      await apiRequest(`/segredos/${segredo.id}/campos`, { token, method: "PUT", body: JSON.stringify(corpo) });
      toast({ title: "Campos salvos", description: "As próximas execuções já recebem os valores novos.", kind: "success" });
      setLinhas(null); setExpira(null);
      await onSalvo();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open={!!segredo} onClose={fechar} title="Editar campos" description={segredo ? `${segredo.nome} (${segredo.chave})` : undefined} className="max-w-2xl"
      footer={<><Button variant="ghost" onClick={fechar}>Cancelar</Button><Button onClick={() => void salvar()} disabled={salvando}>{salvando ? "Salvando..." : "Salvar campos"}</Button></>}>
      <div className="space-y-4">
        <p className="rounded-md border border-warning/30 bg-warning/5 p-3 text-sm">
          Campo oculto em branco mantém o valor atual. Valor trocado vale a partir do próximo pedido; execuções que já pegaram seguem com o antigo.
        </p>
        {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
        <EditorDeCampos linhas={atuais} onMudar={setLinhas} />
        <Field><Label htmlFor="campos-expira">Vence em <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Input id="campos-expira" type="datetime-local" value={expira ?? ""} onChange={(e) => setExpira(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
