"use client";

import Link from "next/link";
import { AlertTriangle, LayoutGrid, UsersRound, Workflow } from "lucide-react";

import { useApi } from "@/hooks/use-api";

/*
 * O que a pessoa acessa (12/11/2026): as TELAS vêm do papel, as AUTOMAÇÕES vêm dos times, e as
 * exceções ficam na própria automação. Só leitura: cada bloco leva para onde se muda.
 */

type Tela = { chave: string; nome: string; grupo: string; nivel: "ver" | "gerenciar" };
type CategoriaDoTime = { categoria: string; ver: boolean; executar: boolean; editar: boolean; publicar: boolean };
type NaAutomacao = { automation_id: number; automacao: string | null; acoes: string[] };
type Resumo = {
  papel: { id: number; nome: string; slug: string; telas: Tela[] } | null;
  times: Array<{ id: number; nome: string; ativo: boolean; categorias: CategoriaDoTime[]; automacoes: NaAutomacao[] }>;
  excecoes: NaAutomacao[];
  permissoes_soltas: boolean;
};

const ACOES: Record<string, string> = {
  ver_execucoes: "ver execuções", ver_telas_e_logs: "ver telas e logs", executar: "executar", controlar: "parar e retomar",
  editar_itens: "editar itens",
};

function oQuePode(c: CategoriaDoTime): string {
  return [c.ver && "ver", c.executar && "executar", c.editar && "editar", c.publicar && "publicar"].filter(Boolean).join(", ");
}

export function ResumoDeAcesso({ userId }: { userId: number }) {
  const resumo = useApi<Resumo>(`/acesso/pessoas/${userId}`);
  if (resumo.error) return <p className="text-sm text-destructive">{resumo.error}</p>;
  const r = resumo.data;
  if (!r) return <div className="skeleton h-32 rounded-lg" />;
  const ve = (r.papel?.telas ?? []).filter((t) => t.nivel === "ver");
  const gerencia = (r.papel?.telas ?? []).filter((t) => t.nivel === "gerenciar");

  return (
    <div className="grid gap-4 py-2 lg:grid-cols-3" data-testid="resumo-de-acesso">
      <section className="space-y-2 rounded-lg border border-border bg-card p-4">
        <p className="flex items-center gap-2 font-semibold text-titulo"><LayoutGrid className="h-4 w-4 text-primary" /> Telas</p>
        <p className="text-sm text-muted-foreground">Pelo papel <strong className="text-titulo">{r.papel?.nome ?? "—"}</strong>.</p>
        {gerencia.length > 0 && <p className="text-sm"><span className="font-medium">Vê e altera:</span> {gerencia.map((t) => t.nome).join(", ")}</p>}
        {ve.length > 0 && <p className="text-sm"><span className="font-medium">Só vê:</span> {ve.map((t) => t.nome).join(", ")}</p>}
        {ve.length + gerencia.length === 0 && <p className="text-sm text-muted-foreground">Nenhuma tela.</p>}
        <Link href="/roles" className="inline-block text-sm font-medium text-primary hover:underline">Mudar em Papéis</Link>
      </section>

      <section className="space-y-2 rounded-lg border border-border bg-card p-4">
        <p className="flex items-center gap-2 font-semibold text-titulo"><UsersRound className="h-4 w-4 text-primary" /> Automações (pelos times)</p>
        {r.times.length === 0 ? (
          <p className="text-sm text-muted-foreground">Em nenhum time: não trabalha com nenhuma automação.</p>
        ) : r.times.map((t) => (
          <div key={t.id} className="text-sm">
            <p className="font-medium">{t.nome}{!t.ativo && <span className="ml-1 text-xs text-muted-foreground">(time desligado: não vale)</span>}</p>
            <ul className="ml-4 list-disc text-muted-foreground">
              {t.categorias.map((c) => <li key={c.categoria}>{c.categoria}: {oQuePode(c)}</li>)}
              {t.automacoes.map((a) => <li key={a.automation_id}>{a.automacao ?? `Automação ${a.automation_id}`}: {a.acoes.map((x) => ACOES[x] ?? x).join(", ")}</li>)}
              {t.categorias.length + t.automacoes.length === 0 && <li>nada ainda</li>}
            </ul>
          </div>
        ))}
        <Link href="/teams" className="inline-block text-sm font-medium text-primary hover:underline">Mudar em Times</Link>
      </section>

      <section className="space-y-2 rounded-lg border border-border bg-card p-4">
        <p className="flex items-center gap-2 font-semibold text-titulo"><Workflow className="h-4 w-4 text-primary" /> Exceções</p>
        <p className="text-sm text-muted-foreground">Acesso dado direto à pessoa, na aba Acessos de uma automação.</p>
        {r.excecoes.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma.</p> : (
          <ul className="ml-4 list-disc text-sm">
            {r.excecoes.map((a) => (
              <li key={a.automation_id}>
                <Link href={`/automations/${a.automation_id}`} className="hover:underline">{a.automacao ?? `Automação ${a.automation_id}`}</Link>:
                {" "}{a.acoes.map((x) => ACOES[x] ?? x).join(", ")}
              </li>
            ))}
          </ul>
        )}
        {r.permissoes_soltas && (
          <p className="flex items-start gap-2 rounded-md bg-warning/10 p-2 text-sm text-warning">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            Ainda há permissões antigas soltas nesta pessoa. Elas continuam valendo; ponha a pessoa num time e peça para retirá-las.
          </p>
        )}
      </section>
    </div>
  );
}
