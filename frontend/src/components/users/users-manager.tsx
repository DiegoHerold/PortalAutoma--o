"use client";

import { Fragment, useState } from "react";
import { ChevronDown, KeyRound, Pencil, Plus, ShieldCheck, Trash2, Users as UsersIcon } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Select, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { User } from "@/types/user";
import type { Role } from "@/types/role";
import type { TeamResponse } from "@/types/access";
import { ResumoDeAcesso } from "@/components/users/resumo-de-acesso";

/*
 * Usuários (12/11/2026, etapa 3): cada pessoa tem UM papel (quais telas) e os TIMES dela (em quais
 * automações). Permissão por categoria não fica mais na pessoa: fica no time.
 */
type TimeDaPessoa = { id: number; nome: string; ativo: boolean };

const emptyForm = { name: "", email: "", role_id: "", is_active: true, times: [] as number[] };

export function UsersManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const users = useApi<User[]>("/users");
  const roles = useApi<Role[]>("/roles");
  const teams = useApi<TeamResponse[]>("/teams");
  const timesDasPessoas = useApi<{ times: Record<string, TimeDaPessoa[]> }>("/acesso/pessoas");

  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState(emptyForm);

  const list = users.data ?? [];

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setModalOpen(true);
  }

  async function openEdit(user: User) {
    setEditing(user);
    const base = { name: user.name, email: user.email, role_id: String(user.role.id), is_active: user.is_active };
    setForm({ ...base, times: [] });
    setModalOpen(true);
    try {
      const r = await apiRequest<{ times: Array<{ id: number }> }>(`/users/${user.id}/times`, { token });
      setForm((atual) => ({ ...atual, times: r.times.map((t) => t.id) }));
    } catch {
      // sem acesso aos times: o formulário segue sem eles
    }
  }

  function alternarTime(id: number) {
    setForm((atual) => ({ ...atual, times: atual.times.includes(id) ? atual.times.filter((t) => t !== id) : [...atual.times, id] }));
  }

  async function saveUser() {
    if (!token || !form.role_id) return;
    setSubmitting(true);
    try {
      const body = {
        name: form.name,
        email: form.email,
        role_id: Number(form.role_id),
        is_active: form.is_active,
        // Sem senha: a pessoa recebe o convite por e-mail e cria a dela (13/11/2026).
      };
      const salvo = await apiRequest<User>(editing ? `/users/${editing.id}` : "/users", {
        method: editing ? "PUT" : "POST",
        token,
        body: JSON.stringify(body),
      });
      if (teams.data) {
        await apiRequest(`/users/${salvo.id ?? editing?.id}/times`, { method: "PUT", token, body: JSON.stringify({ times: form.times }) });
      }
      const convite = salvo.convite_enviado;
      toast({ title: editing ? "Usuário atualizado" : "Usuário criado",
        description: editing ? undefined : convite ? `Mandamos o convite para ${form.email}: a pessoa cria a senha pelo link (vale 48 h).`
          : "O convite não saiu (envio de e-mail desligado ou e-mail que não recebe). Use \"Mandar link de senha\" depois.",
        kind: editing || convite ? "success" : "info" });
      setForm(emptyForm);
      setEditing(null);
      setModalOpen(false);
      await Promise.all([users.refetch(), timesDasPessoas.refetch()]);
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  /** Convite (quem ainda não criou a senha) ou link para criar uma senha nova. O link vale 48 h. */
  async function mandarLink(user: User) {
    if (!token) return;
    try {
      await apiRequest(`/users/${user.id}/convite`, { method: "POST", token });
      toast({ title: "Link mandado", description: `${user.email} recebe um e-mail para criar a senha (vale 48 h).`, kind: "success" });
    } catch (err) {
      toast({ title: "Não foi possível mandar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function removeUser(user: User) {
    if (!token) return;
    if (!window.confirm(`Apagar o usuário "${user.name}"?`)) return;
    try {
      await apiRequest<void>(`/users/${user.id}`, { method: "DELETE", token });
      toast({ title: "Usuário apagado", kind: "success" });
      await users.refetch();
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Novo usuário
        </Button>
      </div>

      {users.error ? (
        <ErrorState message={users.error} onRetry={users.refetch} />
      ) : users.loading ? (
        <Skeleton className="h-64 rounded-lg" />
      ) : list.length === 0 ? (
        <EmptyState icon={UsersIcon} title="Sem usuários" description="Crie o primeiro usuário." />
      ) : (
        <div className="rounded-xl border border-border bg-card">
          <Table>
            <THead>
              <TR className="hover:bg-transparent">
                <TH>Nome</TH>
                <TH>E-mail</TH>
                <TH>Papel</TH>
                <TH>Times</TH>
                <TH>Status</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {list.map((user) => (
                <Fragment key={user.id}>
                  <TR>
                    <TD className="font-medium">{user.name}</TD>
                    <TD className="text-sm text-muted-foreground">{user.email}</TD>
                    <TD>
                      <Badge tone="primary">{user.role.name}</Badge>
                    </TD>
                    <TD>
                      <div className="flex flex-wrap gap-1" data-testid="times-da-pessoa">
                        {(timesDasPessoas.data?.times?.[String(user.id)] ?? []).map((t) => (
                          <Badge key={t.id} tone={t.ativo ? "outline" : "neutral"}>{t.nome}</Badge>
                        ))}
                        {(timesDasPessoas.data?.times?.[String(user.id)] ?? []).length === 0 && (
                          <span className="text-sm text-muted-foreground">nenhum</span>
                        )}
                      </div>
                    </TD>
                    <TD>
                      {user.aguardando_senha && user.is_active ? (
                        <Badge tone="warning">Aguardando criar senha</Badge>
                      ) : (
                        <Badge tone={user.is_active ? "success" : "neutral"}>{user.is_active ? "Ativo" : "Inativo"}</Badge>
                      )}
                    </TD>
                    <TD>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setExpanded(expanded === user.id ? null : user.id)}
                          title="O que acessa" aria-label={`O que ${user.name} acessa`}
                        >
                          <ShieldCheck className="h-4 w-4" />
                          <ChevronDown className={cn("h-3 w-3 transition-transform", expanded === user.id && "rotate-180")} />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => void mandarLink(user)} disabled={!user.is_active}
                          title="Mandar link de senha" aria-label={`Mandar link de senha para ${user.name}`}>
                          <KeyRound className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => void openEdit(user)} title="Editar usuário">
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => removeUser(user)} title="Apagar usuário">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TD>
                  </TR>
                  {expanded === user.id && (
                    <TR className="hover:bg-transparent">
                      <TD colSpan={6} className="bg-muted/30">
                        <ResumoDeAcesso userId={user.id} />
                      </TD>
                    </TR>
                  )}
                </Fragment>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Editar usuário" : "Novo usuário"}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={saveUser}
              disabled={submitting || !form.name || !form.email || !form.role_id}
            >
              {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field>
            <Label htmlFor="u-name">Nome</Label>
            <Input id="u-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="u-email">E-mail</Label>
            <Input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          {!editing && (
            <p className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
              A pessoa recebe um e-mail para criar a própria senha (o link vale 48 horas). Ninguém mais conhece a senha dela.
            </p>
          )}
          <Field>
            <Label htmlFor="u-role">Papel <span className="font-normal text-muted-foreground">— quais telas a pessoa usa</span></Label>
            <Select id="u-role" value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
              <option value="">Selecione...</option>
              {roles.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
          </Field>
          {(teams.data ?? []).length > 0 && (
            <fieldset className="space-y-2" data-testid="times-do-usuario">
              <legend className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Times</legend>
              <p className="text-xs text-muted-foreground">Em quais automações a pessoa trabalha: ela ganha o que os times ativos dão.</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {(teams.data ?? []).map((t) => (
                  <label key={t.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
                    <input type="checkbox" className="h-4 w-4 accent-primary" checked={form.times.includes(t.id)}
                      onChange={() => alternarTime(t.id)} aria-label={`Time ${t.name}`} />
                    <span className="truncate">{t.name}</span>
                    {t.status !== "active" && <span className="ml-auto text-xs text-muted-foreground">inativo</span>}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="h-4 w-4 accent-primary"
            />
            Usuário ativo
          </label>
        </div>
      </Modal>
    </div>
  );
}
