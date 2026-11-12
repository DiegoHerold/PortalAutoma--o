"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, UserMinus } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useToast } from "@/components/ui/toast";
import type { TeamResponse } from "@/types/access";
import type { Category } from "@/types/category";
import type { User } from "@/types/user";
import type { Automation } from "@/types/automation";

type Membro = { id: number; nome: string; email: string; ativo: boolean };
type Categoria = {
  category_id: number; categoria?: string; can_view: boolean; can_execute: boolean;
  can_create?: boolean; can_edit?: boolean; can_delete?: boolean; can_approve?: boolean;
};
type Marca = "can_view" | "can_execute" | "can_edit" | "can_approve";
/** O que o time pode nas automações da categoria. "Editar" vale pelas três de cadastro (criar, editar, apagar). */
const MARCAS: Array<{ campo: Marca; rotulo: string; dica: string }> = [
  { campo: "can_view", rotulo: "Ver", dica: "ver as automações e as execuções" },
  { campo: "can_execute", rotulo: "Executar", dica: "pedir execução" },
  { campo: "can_edit", rotulo: "Editar", dica: "criar, editar e apagar o cadastro das automações" },
  { campo: "can_approve", rotulo: "Publicar", dica: "publicar versões" },
];
type NaAutomacao = { automation_id: number; automacao: string; acoes: string[] };
type Detalhes = { membros: Membro[]; categorias: Categoria[]; automacoes: NaAutomacao[]; acoes_possiveis: string[] };

const ACAO: Record<string, string> = {
  ver_execucoes: "Ver execuções", ver_telas_e_logs: "Ver telas e logs", executar: "Executar",
  controlar: "Controlar", editar_itens: "Editar itens",
};

/**
 * O time por dentro: quem é membro e o que o time dá a eles. Por categoria (ver e executar
 * todas as automações da categoria) e por automação (as mesmas ações da tela "Acesso a telas e
 * logs"). Quem entra ganha; quem sai perde; time desabilitado não dá nada.
 */
export function TimeDetalhes({ time, fechar }: { time: TeamResponse | null; fechar: () => void }) {
  return (
    <Sheet open={!!time} onClose={fechar} title={time?.name} description={time && time.status !== "active"
      ? "Time desabilitado: os membros não ganham nada dele enquanto estiver assim." : "Membros e permissões do time"}
      widthClassName="w-full sm:max-w-2xl">
      {time && <Conteudo time={time} />}
    </Sheet>
  );
}

function Conteudo({ time }: { time: TeamResponse }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const detalhes = useApi<Detalhes>(`/teams/${time.id}/detalhes`);
  const usuarios = useApi<User[]>("/users");
  const categorias = useApi<Category[]>("/categories");
  const automacoes = useApi<Automation[]>("/automations");
  const [novoMembro, setNovoMembro] = useState("");
  const [cats, setCats] = useState<Categoria[]>([]);
  const [novaAutomacao, setNovaAutomacao] = useState("");
  const [marcadas, setMarcadas] = useState<Record<number, string[]>>({});  // marca na hora; a resposta confirma

  useEffect(() => {
    if (detalhes.data) setCats(detalhes.data.categorias);
  }, [detalhes.data]);

  async function chamar(caminho: string, metodo: string, corpo: unknown, ok: string) {
    try {
      await apiRequest(caminho, { method: metodo, token, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
      toast({ title: ok, kind: "success" });
      await detalhes.refetch();
      return true;
    } catch (err) {
      toast({ title: "Não foi possível", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return false;
    }
  }

  if (detalhes.error && !detalhes.data) return <ErrorState message={detalhes.error} onRetry={() => void detalhes.refetch()} />;
  if (!detalhes.data) return <div className="skeleton h-64 rounded-xl" />;
  const d = detalhes.data;
  const membros = new Set(d.membros.map((m) => m.id));
  const candidatos = (usuarios.data ?? []).filter((u) => !membros.has(u.id));
  const catMudou = JSON.stringify(cats) !== JSON.stringify(d.categorias);
  const comAcesso = new Set(d.automacoes.map((a) => a.automation_id));

  function marcarCategoria(id: number, campo: Marca, valor: boolean) {
    setCats((atuais) => {
      const atual: Categoria = atuais.find((c) => c.category_id === id) ?? { category_id: id, can_view: false, can_execute: false };
      let nova: Categoria = { ...atual, [campo]: valor };
      if (campo === "can_edit") nova = { ...nova, can_create: valor, can_delete: valor };
      if (campo !== "can_view" && valor) nova = { ...nova, can_view: true };  // quem executa, edita ou publica vê
      if (campo === "can_view" && !valor) {
        nova = { ...nova, can_execute: false, can_create: false, can_edit: false, can_delete: false, can_approve: false };
      }
      const resto = atuais.filter((c) => c.category_id !== id);
      const alguma = nova.can_view || nova.can_execute || nova.can_edit || nova.can_approve || nova.can_create || nova.can_delete;
      return alguma ? [...resto, nova].sort((a, b) => a.category_id - b.category_id) : resto;
    });
  }

  const acoesAgora = (a: NaAutomacao) => marcadas[a.automation_id] ?? a.acoes;

  async function marcarAcao(a: NaAutomacao, acao: string, marcar: boolean) {
    const atuais = acoesAgora(a);
    const novas = marcar ? [...new Set([...atuais, acao])] : atuais.filter((x) => x !== acao);
    setMarcadas((m) => ({ ...m, [a.automation_id]: novas }));
    await chamar(`/automations/${a.automation_id}/acessos`, "PUT", { team_id: time.id, acoes: novas }, "Acesso salvo");
    setMarcadas((m) => {  // vale o que o Portal gravou (recarregado em chamar)
      const resto = { ...m };
      delete resto[a.automation_id];
      return resto;
    });
  }

  return (
    <div className="space-y-8" data-testid="time-detalhes">
      <section className="space-y-3">
        <h3 className="titulo-condensado text-xl">Membros ({d.membros.length})</h3>
        <div className="flex gap-2">
          <select value={novoMembro} onChange={(e) => setNovoMembro(e.target.value)} aria-label="Pessoa para adicionar"
            className="h-10 flex-1 rounded-md border border-input bg-background px-3">
            <option value="">Escolha uma pessoa…</option>
            {candidatos.map((u) => <option key={u.id} value={u.id}>{u.name} · {u.email}</option>)}
          </select>
          <Button disabled={!novoMembro} onClick={() => void chamar(`/teams/${time.id}/membros`, "POST",
            { usuarios: [Number(novoMembro)] }, "Membro adicionado").then((ok) => ok && setNovoMembro(""))}>
            <Plus className="h-4 w-4" /> Adicionar
          </Button>
        </div>
        {d.membros.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-muted-foreground">Ninguém no time ainda.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {d.membros.map((m) => (
              <li key={m.id} className="flex items-center gap-3 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{m.nome}{!m.ativo && <span className="ml-2 text-xs text-muted-foreground">inativo</span>}</p>
                  <p className="truncate text-sm text-muted-foreground">{m.email}</p>
                </div>
                <Button variant="ghost" size="icon" aria-label={`Tirar ${m.nome} do time`}
                  onClick={() => void chamar(`/teams/${time.id}/membros/${m.id}`, "DELETE", undefined, "Membro removido")}>
                  <UserMinus className="h-4 w-4 text-destructive" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="titulo-condensado text-xl">Por categoria</h3>
            <p className="text-sm text-muted-foreground">Vale para todas as automações da categoria. É aqui que se dá acesso às automações; as telas vêm do papel.</p>
          </div>
          <Button size="sm" disabled={!catMudou} onClick={() => void chamar(`/teams/${time.id}/categorias`, "PUT",
            { categorias: cats.map(({ category_id, can_view, can_execute, can_create, can_edit, can_delete, can_approve }) =>
              ({ category_id, can_view, can_execute, can_create: !!can_create, can_edit: !!can_edit, can_delete: !!can_delete,
                 can_approve: !!can_approve })) }, "Permissões salvas")}>
            Salvar
          </Button>
        </div>
        <ul className="divide-y divide-border rounded-lg border border-border" data-testid="time-categorias">
          {(categorias.data ?? []).map((c) => {
            const atual = cats.find((x) => x.category_id === c.id);
            return (
              <li key={c.id} className="flex flex-wrap items-center gap-4 px-3 py-2">
                <span className="min-w-0 flex-1 truncate font-medium">{c.name}</span>
                {MARCAS.map((m) => (
                  <label key={m.campo} className="flex items-center gap-1.5 text-sm" title={m.dica}>
                    <input type="checkbox" className="h-4 w-4 accent-primary" checked={!!atual?.[m.campo]}
                      onChange={(e) => marcarCategoria(c.id, m.campo, e.target.checked)} aria-label={`${m.rotulo} ${c.name}`} /> {m.rotulo}
                  </label>
                ))}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="titulo-condensado text-xl">Por automação</h3>
          <p className="text-sm text-muted-foreground">O mesmo de "Acesso a telas e logs" de cada automação. Cada marca vale na hora.</p>
        </div>
        <div className="flex gap-2">
          <select value={novaAutomacao} onChange={(e) => setNovaAutomacao(e.target.value)} aria-label="Automação para dar acesso"
            className="h-10 flex-1 rounded-md border border-input bg-background px-3">
            <option value="">Escolha uma automação…</option>
            {(automacoes.data ?? []).filter((a) => !comAcesso.has(a.id)).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <Button disabled={!novaAutomacao} onClick={() => void chamar(`/automations/${novaAutomacao}/acessos`, "PUT",
            { team_id: time.id, acoes: ["ver_execucoes"] }, "Acesso dado").then((ok) => ok && setNovaAutomacao(""))}>
            <Plus className="h-4 w-4" /> Dar acesso
          </Button>
        </div>
        {d.automacoes.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-muted-foreground">Nenhuma automação com acesso pelo time.</p>
        ) : (
          <ul className="space-y-3" data-testid="time-automacoes">
            {d.automacoes.map((a) => (
              <li key={a.automation_id} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{a.automacao}</p>
                  <Button variant="ghost" size="icon" aria-label={`Tirar o acesso a ${a.automacao}`}
                    onClick={() => void chamar(`/automations/${a.automation_id}/acessos`, "PUT", { team_id: time.id, acoes: [] }, "Acesso retirado")}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
                  {d.acoes_possiveis.map((acao) => (
                    <label key={acao} className="flex items-center gap-1.5 text-sm">
                      <input type="checkbox" className="h-4 w-4 accent-primary" checked={acoesAgora(a).includes(acao)}
                        aria-label={`${ACAO[acao] ?? acao} em ${a.automacao}`}
                        onChange={(e) => void marcarAcao(a, acao, e.target.checked)} />
                      {ACAO[acao] ?? acao}
                    </label>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
