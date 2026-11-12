"use client";

import { Fragment, useMemo, useState } from "react";
import { Pencil, Plus, Trash2, Users } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";

/*
 * Papéis globais (12/11/2026): uma tabela com as funcionalidades do Portal (linhas, agrupadas como
 * no menu) e os papéis (colunas). Cada célula: — (não entra), Ver ou Gerenciar (vê e altera).
 * O papel diz QUAIS TELAS a pessoa usa; o time diz EM QUAIS AUTOMAÇÕES. Só administradores mudam.
 */

type Nivel = "ver" | "gerenciar";
type Papel = {
  id: number; nome: string; slug: string; descricao: string | null; sistema: boolean; pessoas: number;
  funcionalidades: Record<string, Nivel>; editavel: boolean; pode_apagar: boolean;
};
type Funcionalidade = { chave: string; nome: string; grupo: string; href: string; niveis: Nivel[]; o_que_gerenciar: string | null };
type Formulario = { id: number | null; nome: string; descricao: string; baseado_em: string };

const ROTULO: Record<string, string> = { "": "—", ver: "Ver", gerenciar: "Gerenciar" };
const TOM: Record<string, string> = {
  "": "text-muted-foreground",
  ver: "bg-info/10 text-info font-medium",
  gerenciar: "bg-primary/15 text-primary font-semibold",
};

export function RolesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const papeis = useApi<{ papeis: Papel[]; pode_editar: boolean }>("/papeis");
  const catalogo = useApi<{ funcionalidades: Funcionalidade[] }>("/papeis/funcionalidades");
  const [form, setForm] = useState<Formulario | null>(null);
  const [apagando, setApagando] = useState<Papel | null>(null);
  const [substituto, setSubstituto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [mudancas, setMudancas] = useState<Record<number, Record<string, Nivel>>>({});

  const funcionalidades = useMemo(() => (Array.isArray(catalogo.data?.funcionalidades) ? catalogo.data.funcionalidades : []),
    [catalogo.data]);
  const grupos = useMemo(() => {
    const mapa = new Map<string, Funcionalidade[]>();
    for (const f of funcionalidades) mapa.set(f.grupo, [...(mapa.get(f.grupo) ?? []), f]);
    return [...mapa.entries()];
  }, [funcionalidades]);

  async function enviar(caminho: string, metodo: string, corpo: unknown, sucesso: string | null): Promise<boolean> {
    setOcupado(true);
    try {
      await apiRequest(caminho, { token, method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      if (sucesso) toast({ title: sucesso, kind: "success" });
      await papeis.refetch();
      return true;
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return false;
    } finally {
      setOcupado(false);
    }
  }

  /** Muda uma célula e salva na hora (a configuração é rara: um clique, um registro na auditoria). */
  async function mudar(papel: Papel, f: Funcionalidade, nivel: string) {
    const atual = { ...papel.funcionalidades, ...(mudancas[papel.id] ?? {}) };
    const nova: Record<string, Nivel | null> = { ...atual, [f.chave]: (nivel || null) as Nivel | null };
    setMudancas((m) => ({ ...m, [papel.id]: Object.fromEntries(Object.entries(nova).filter(([, v]) => v)) as Record<string, Nivel> }));
    const ok = await enviar(`/papeis/${papel.id}`, "PUT", { funcionalidades: nova }, null);
    setMudancas((m) => { const resto = { ...m }; delete resto[papel.id]; return resto; });
    if (ok) toast({ title: `${papel.nome}: ${f.nome} em "${ROTULO[nivel]}"`, kind: "success" });
  }

  async function salvar() {
    if (!form) return;
    const ok = form.id
      ? await enviar(`/papeis/${form.id}`, "PUT", { nome: form.nome, descricao: form.descricao }, "Papel salvo")
      : await enviar("/papeis", "POST", { nome: form.nome, descricao: form.descricao,
          ...(form.baseado_em ? { baseado_em: Number(form.baseado_em) } : {}) }, "Papel criado");
    if (ok) setForm(null);
  }

  async function apagar() {
    if (!apagando) return;
    const ok = await enviar(`/papeis/${apagando.id}${substituto ? `?substituto=${substituto}` : ""}`, "DELETE", undefined,
      "Papel apagado");
    if (ok) setApagando(null);
  }

  if (papeis.error) return <ErrorState message={papeis.error} onRetry={papeis.refetch} />;
  if (!papeis.data || !Array.isArray(papeis.data.papeis) || !catalogo.data) return <Skeleton className="h-[60vh] rounded-xl" />;
  const lista = papeis.data.papeis;
  const editar = papeis.data.pode_editar;
  const tabelaDe = (p: Papel) => ({ ...p.funcionalidades, ...(mudancas[p.id] ?? {}) });

  return (
    <div className="space-y-5" data-testid="papeis">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl space-y-1 text-sm text-muted-foreground">
          <p><strong className="text-titulo">Ver</strong>: a pessoa abre a tela. <strong className="text-titulo">Gerenciar</strong>: vê e altera (criar, editar, apagar).</p>
          <p>O papel diz quais telas a pessoa usa; em quais automações ela trabalha é o time que diz.
            {!editar && " Só administradores mudam os papéis."}</p>
        </div>
        {editar && <Button onClick={() => setForm({ id: null, nome: "", descricao: "", baseado_em: "" })}><Plus className="h-4 w-4" /> Novo papel</Button>}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
        <table className="w-full border-collapse text-sm" data-testid="tabela-de-papeis">
          <thead>
            <tr className="border-b border-border">
              <th className="sticky left-0 z-10 min-w-[15rem] bg-card px-4 py-3 text-left align-bottom font-semibold text-muted-foreground">
                Funcionalidade
              </th>
              {lista.map((p) => (
                <th key={p.id} className="min-w-[9.5rem] px-3 py-3 text-left align-bottom" data-papel={p.slug}>
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0">
                      <p className="truncate text-base font-semibold text-titulo" title={p.descricao ?? undefined}>{p.nome}</p>
                      <p className="flex items-center gap-1 text-xs font-normal text-muted-foreground">
                        <Users className="h-3.5 w-3.5" /> {p.pessoas}{p.sistema ? " · sistema" : ""}
                      </p>
                    </div>
                    {editar && (
                      <div className="flex shrink-0">
                        <button className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={`Editar ${p.nome}`}
                          onClick={() => setForm({ id: p.id, nome: p.nome, descricao: p.descricao ?? "", baseado_em: "" })}>
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        {p.pode_apagar && (
                          <button className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive" aria-label={`Apagar ${p.nome}`}
                            onClick={() => { setApagando(p); setSubstituto(""); }}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grupos.map(([grupo, itens]) => (
              <Fragment key={grupo}>
                <tr className="bg-muted/50">
                  <td colSpan={lista.length + 1} className="sticky left-0 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    {grupo}
                  </td>
                </tr>
                {itens.map((f) => (
                  <tr key={f.chave} className="border-t border-border/60 hover:bg-muted/30" data-funcionalidade={f.chave}>
                    <td className="sticky left-0 z-10 bg-card px-4 py-2">
                      <p className="font-medium text-titulo">{f.nome}</p>
                      {f.o_que_gerenciar && <p className="text-xs text-muted-foreground">Gerenciar: {f.o_que_gerenciar}</p>}
                    </td>
                    {lista.map((p) => {
                      const nivel = tabelaDe(p)[f.chave] ?? "";
                      if (!editar || !p.editavel) {
                        return (
                          <td key={p.id} className="px-3 py-2">
                            <span className={cn("inline-block rounded-md px-2 py-0.5", TOM[nivel])}>{p.editavel ? ROTULO[nivel] : "Tudo"}</span>
                          </td>
                        );
                      }
                      return (
                        <td key={p.id} className="px-3 py-2">
                          <select value={nivel} disabled={ocupado} aria-label={`${p.nome}: ${f.nome}`}
                            onChange={(e) => void mudar(p, f, e.target.value)}
                            className={cn("h-9 w-full rounded-md border border-input px-2 text-sm", nivel ? TOM[nivel] : "bg-background")}>
                            <option value="">—</option>
                            {f.niveis.map((n) => <option key={n} value={n}>{ROTULO[n]}</option>)}
                          </select>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={form !== null} onClose={() => setForm(null)} title={form?.id ? `Editar ${form.nome || "papel"}` : "Novo papel"}
        footer={<>
          <Button variant="ghost" onClick={() => setForm(null)}>Voltar</Button>
          <Button disabled={ocupado || !form?.nome.trim()} onClick={() => void salvar()}>{form?.id ? "Salvar" : "Criar papel"}</Button>
        </>}>
        {form && (
          <div className="space-y-4">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Nome</span>
              <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} maxLength={100}
                className="h-11 w-full rounded-lg border border-input bg-background px-3" aria-label="Nome do papel" />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Descrição</span>
              <input value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} maxLength={500}
                className="h-11 w-full rounded-lg border border-input bg-background px-3" aria-label="Descrição do papel" />
            </label>
            {!form.id && (
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">Baseado em</span>
                <select value={form.baseado_em} onChange={(e) => setForm({ ...form, baseado_em: e.target.value })} aria-label="Baseado em"
                  className="h-11 w-full rounded-lg border border-input bg-background px-3">
                  <option value="">Nenhum (começa só com o Painel)</option>
                  {lista.filter((p) => p.slug !== "admin").map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
                </select>
                <span className="block text-xs text-muted-foreground">Copia a coluna do papel escolhido. Depois é só ajustar na tabela.</span>
              </label>
            )}
          </div>
        )}
      </Modal>

      <Modal open={apagando !== null} onClose={() => setApagando(null)} title={`Apagar ${apagando?.nome ?? "papel"}?`}
        footer={<>
          <Button variant="ghost" onClick={() => setApagando(null)}>Voltar</Button>
          <Button variant="destructive" disabled={ocupado || Boolean(apagando?.pessoas && !substituto)} onClick={() => void apagar()}>
            Apagar papel
          </Button>
        </>}>
        {apagando && (apagando.pessoas > 0 ? (
          <label className="block space-y-2 text-sm">
            <span>{apagando.pessoas} pessoa(s) têm este papel. Para qual papel elas vão?</span>
            <select value={substituto} onChange={(e) => setSubstituto(e.target.value)} aria-label="Papel substituto"
              className="h-11 w-full rounded-lg border border-input bg-background px-3">
              <option value="">Escolha…</option>
              {lista.filter((p) => p.id !== apagando.id).map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </select>
          </label>
        ) : (
          <p className="text-sm">Ninguém tem este papel. Ele sai da tabela e não pode ser recuperado.</p>
        ))}
      </Modal>
    </div>
  );
}
