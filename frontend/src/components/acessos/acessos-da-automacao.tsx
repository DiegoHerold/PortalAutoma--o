"use client";

import { useState } from "react";
import { ShieldCheck, UserPlus, Users } from "lucide-react";

import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PageTitle } from "@/components/shared/page-title";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import type { TeamResponse } from "@/types/access";
import type { User } from "@/types/user";

type Concessao = {
  id: string;
  user_id: number | null;
  team_id: number | null;
  nome: string | null;
  email: string | null;
  acoes: string[];
  atualizada_em: string | null;
};

const ACOES: Array<{ chave: string; nome: string; explica: string }> = [
  { chave: "ver_execucoes", nome: "Ver execuções", explica: "Andamento, etapas, estimativas e resultado" },
  { chave: "ver_telas_e_logs", nome: "Ver telas e logs", explica: "Imagens de cada passo e o log ao vivo (dados de clientes)" },
  { chave: "editar_itens", nome: "Editar itens", explica: "Cadastro de itens da automação" },
  { chave: "executar", nome: "Executar", explica: "Pedir execução" },
  { chave: "controlar", nome: "Controlar", explica: "Parar e retomar execuções" },
];

export function AcessosDaAutomacao({ id }: { id: string }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const lista = useApi<{ acoes_possiveis: string[]; concessoes: Concessao[] }>(`/automations/${id}/acessos`);
  const usuarios = useApi<User[]>("/users");
  const times = useApi<TeamResponse[]>("/teams");
  const [novo, setNovo] = useState("");
  const [salvando, setSalvando] = useState<string | null>(null);

  async function definir(destino: { user_id?: number; team_id?: number }, acoes: string[], chave: string) {
    setSalvando(chave);
    try {
      await apiRequest(`/automations/${id}/acessos`, { method: "PUT", token, body: JSON.stringify({ ...destino, acoes }) });
      await lista.refetch();
      toast({ title: acoes.length ? "Acesso atualizado" : "Acesso retirado", kind: "success" });
    } catch (err) {
      toast({ title: "Não foi possível salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSalvando(null);
    }
  }

  const concessoes = lista.data?.concessoes ?? [];
  const jaTem = new Set(concessoes.map((c) => (c.user_id != null ? `u:${c.user_id}` : `t:${c.team_id}`)));
  const opcoes = [
    ...(usuarios.data ?? []).filter((u) => !jaTem.has(`u:${u.id}`)).map((u) => ({ valor: `u:${u.id}`, texto: `${u.name} · ${u.email}` })),
    ...(times.data ?? []).filter((t) => !jaTem.has(`t:${t.id}`)).map((t) => ({ valor: `t:${t.id}`, texto: `Time ${t.name}` })),
  ];

  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Acesso"
        title="Quem pode o quê nesta automação"
        description="Telas e logs mostram dados de clientes: só quem recebe “Ver telas e logs” enxerga as imagens e o log. Toda mudança vai para a auditoria."
      />

      {lista.error && !lista.data ? (
        <ErrorState message={lista.error} onRetry={() => void lista.refetch()} />
      ) : (
        <>
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4 shadow-sm sm:flex-row sm:items-center">
            <UserPlus className="hidden h-5 w-5 text-muted-foreground sm:block" />
            <select
              value={novo}
              onChange={(e) => setNovo(e.target.value)}
              className="h-10 flex-1 rounded-md border border-input bg-card px-3 text-sm"
              aria-label="Pessoa ou time"
            >
              <option value="">Escolha uma pessoa ou um time…</option>
              {opcoes.map((o) => (
                <option key={o.valor} value={o.valor}>
                  {o.texto}
                </option>
              ))}
            </select>
            <Button
              disabled={!novo || salvando !== null}
              onClick={() => {
                const [tipo, valor] = novo.split(":");
                void definir(tipo === "u" ? { user_id: Number(valor) } : { team_id: Number(valor) }, ["ver_execucoes"], novo).then(() => setNovo(""));
              }}
            >
              Dar acesso
            </Button>
          </div>

          {concessoes.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="Nenhum acesso próprio"
              description="Por enquanto valem só as permissões antigas da categoria: elas dão “Ver execuções” e “Executar”, nunca telas e logs."
            />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-muted text-left text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2.5">Pessoa ou time</th>
                    {ACOES.map((a) => (
                      <th key={a.chave} className="px-3 py-2.5 text-center" title={a.explica}>
                        {a.nome}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {concessoes.map((c) => {
                    const chave = c.user_id != null ? `u:${c.user_id}` : `t:${c.team_id}`;
                    const destino = c.user_id != null ? { user_id: c.user_id } : { team_id: c.team_id ?? undefined };
                    return (
                      <tr key={c.id} className={cn(salvando === chave && "opacity-60")}>
                        <td className="px-4 py-2.5">
                          <p className="flex items-center gap-1.5 font-medium text-titulo">
                            {c.team_id != null && <Users className="h-3.5 w-3.5 text-muted-foreground" />}
                            {c.nome ?? "—"}
                          </p>
                          {c.email && <p className="text-xs text-muted-foreground">{c.email}</p>}
                        </td>
                        {ACOES.map((a) => (
                          <td key={a.chave} className="px-3 py-2.5 text-center">
                            <input
                              type="checkbox"
                              className="h-4 w-4 accent-[hsl(var(--primary))]"
                              checked={c.acoes.includes(a.chave)}
                              disabled={salvando !== null}
                              aria-label={`${a.nome} para ${c.nome ?? "—"}`}
                              onChange={(e) => {
                                const acoes = e.target.checked ? [...c.acoes, a.chave] : c.acoes.filter((x) => x !== a.chave);
                                void definir(destino, acoes, chave);
                              }}
                            />
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <ul className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-3">
            {ACOES.map((a) => (
              <li key={a.chave}>
                <strong className="text-foreground">{a.nome}:</strong> {a.explica}.
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
