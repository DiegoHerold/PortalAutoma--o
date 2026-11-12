"use client";

import { useMemo, useState } from "react";
import { Pencil, Plus, ShieldCheck, Trash2, Users } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";

/*
 * Papéis globais (12/11/2026): cada papel diz quais abas do menu a pessoa vê. Só administradores
 * criam, mudam e apagam. Desligar uma aba tira o acesso a ela; ligar dá a leitura dela.
 */

type Papel = {
  id: number; nome: string; slug: string; descricao: string | null; sistema: boolean; pessoas: number;
  abas: string[]; pode_mudar_abas: boolean; pode_apagar: boolean;
};
type Aba = { chave: string; rotulo: string; grupo: string };
type Formulario = { id: number | null; nome: string; descricao: string; abas: string[]; baseado_em: string; pode_mudar_abas: boolean };

const VAZIO: Formulario = { id: null, nome: "", descricao: "", abas: [], baseado_em: "", pode_mudar_abas: true };

export function RolesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const papeis = useApi<{ papeis: Papel[]; pode_editar: boolean }>("/papeis");
  const abas = useApi<{ abas: Aba[] }>("/papeis/abas");
  const [form, setForm] = useState<Formulario | null>(null);
  const [apagando, setApagando] = useState<Papel | null>(null);
  const [substituto, setSubstituto] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const grupos = useMemo(() => {
    const mapa = new Map<string, Aba[]>();
    for (const a of Array.isArray(abas.data?.abas) ? abas.data.abas : []) mapa.set(a.grupo, [...(mapa.get(a.grupo) ?? []), a]);
    return [...mapa.entries()];
  }, [abas.data]);
  const rotulo = (chave: string) => abas.data?.abas.find((a) => a.chave === chave)?.rotulo ?? chave;

  async function enviar(caminho: string, metodo: string, corpo: unknown, sucesso: string): Promise<boolean> {
    setOcupado(true);
    try {
      await apiRequest(caminho, { token, method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      toast({ title: sucesso, kind: "success" });
      await papeis.refetch();
      return true;
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return false;
    } finally {
      setOcupado(false);
    }
  }

  async function salvar() {
    if (!form) return;
    const corpo = { nome: form.nome, descricao: form.descricao, ...(form.pode_mudar_abas ? { abas: form.abas } : {}) };
    const ok = form.id
      ? await enviar(`/papeis/${form.id}`, "PUT", corpo, "Papel salvo")
      : await enviar("/papeis", "POST", { ...corpo, ...(form.baseado_em ? { baseado_em: Number(form.baseado_em) } : {}) },
        "Papel criado");
    if (ok) setForm(null);
  }

  async function apagar() {
    if (!apagando) return;
    const ok = await enviar(`/papeis/${apagando.id}${substituto ? `?substituto=${substituto}` : ""}`, "DELETE", undefined,
      "Papel apagado");
    if (ok) setApagando(null);
  }

  if (papeis.error) return <ErrorState message={papeis.error} onRetry={papeis.refetch} />;
  if (!papeis.data || !Array.isArray(papeis.data.papeis)) {
    return <div className="grid gap-4 lg:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-44 rounded-xl" />)}</div>;
  }
  const lista = papeis.data.papeis;
  const editar = papeis.data.pode_editar;
  const total = abas.data?.abas.length ?? 0;

  return (
    <div className="space-y-5" data-testid="papeis">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted-foreground">
          {editar ? "Desligar uma aba tira o acesso a ela; ligar dá a leitura dela." : "Só administradores mudam os papéis."}
        </p>
        {editar && (
          <Button onClick={() => setForm({ ...VAZIO })}><Plus className="h-4 w-4" /> Novo papel</Button>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {lista.map((p) => (
          <article key={p.id} className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm" data-papel={p.slug}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-lg font-semibold text-titulo">
                  <ShieldCheck className="h-5 w-5 text-primary" /> {p.nome}
                  {p.sistema && <Badge tone="outline" className="text-xs">Sistema</Badge>}
                </p>
                <p className="text-sm text-muted-foreground">{p.descricao || "Sem descrição."}</p>
              </div>
              {editar && (
                <div className="flex shrink-0 gap-1">
                  <Button size="sm" variant="ghost" aria-label={`Editar ${p.nome}`}
                    onClick={() => setForm({ id: p.id, nome: p.nome, descricao: p.descricao ?? "", abas: p.abas, baseado_em: "",
                                             pode_mudar_abas: p.pode_mudar_abas })}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  {p.pode_apagar && (
                    <Button size="sm" variant="ghost" aria-label={`Apagar ${p.nome}`} onClick={() => { setApagando(p); setSubstituto(""); }}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              )}
            </div>
            <p className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5"><Users className="h-4 w-4" /> {p.pessoas} pessoa(s)</span>
              <span>{p.pode_mudar_abas ? `${p.abas.length} de ${total} abas` : "Todas as abas"}</span>
            </p>
            {p.pode_mudar_abas && (
              <div className="flex flex-wrap gap-1.5" data-testid="abas-do-papel">
                {p.abas.length === 0 ? <span className="text-sm text-muted-foreground">Só o Painel.</span>
                  : p.abas.map((a) => <span key={a} className="rounded-md bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">{rotulo(a)}</span>)}
              </div>
            )}
          </article>
        ))}
      </div>

      <Modal open={form !== null} onClose={() => setForm(null)} className="max-w-2xl"
        title={form?.id ? `Editar ${form.nome || "papel"}` : "Novo papel"}
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
                <select value={form.baseado_em} aria-label="Baseado em"
                  onChange={(e) => {
                    const base = lista.find((p) => String(p.id) === e.target.value);
                    setForm({ ...form, baseado_em: e.target.value, abas: base ? base.abas : form.abas });
                  }}
                  className="h-11 w-full rounded-lg border border-input bg-background px-3">
                  <option value="">Nenhum (começa só com o Painel)</option>
                  {lista.filter((p) => p.slug !== "admin").map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
                </select>
                <span className="block text-xs text-muted-foreground">Copia o que o papel pode fazer (executar, editar...) e as abas dele.</span>
              </label>
            )}
            <fieldset className="space-y-3">
              <legend className="flex w-full items-center justify-between text-sm font-medium">
                Abas que aparecem
                {form.pode_mudar_abas && (
                  <span className="flex gap-3 text-xs font-normal">
                    <button type="button" className="text-primary hover:underline"
                      onClick={() => setForm({ ...form, abas: (abas.data?.abas ?? []).map((a) => a.chave) })}>Todas</button>
                    <button type="button" className="text-primary hover:underline" onClick={() => setForm({ ...form, abas: [] })}>Nenhuma</button>
                  </span>
                )}
              </legend>
              {!form.pode_mudar_abas ? (
                <p className="text-sm text-muted-foreground">O papel Admin vê todas as abas.</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {grupos.map(([grupo, itens]) => (
                    <div key={grupo} className="space-y-1.5">
                      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{grupo}</p>
                      {itens.map((a) => {
                        const ligada = form.abas.includes(a.chave);
                        return (
                          <label key={a.chave} className={cn("flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-muted",
                            ligada && "font-medium text-titulo")}>
                            <input type="checkbox" checked={ligada} aria-label={a.rotulo}
                              onChange={() => setForm({ ...form, abas: ligada ? form.abas.filter((x) => x !== a.chave) : [...form.abas, a.chave] })} />
                            {a.rotulo}
                          </label>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">O Painel e as Configurações aparecem sempre.</p>
            </fieldset>
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
          <p className="text-sm">Ninguém tem este papel. Ele sai da lista e não pode ser recuperado.</p>
        ))}
      </Modal>
    </div>
  );
}
