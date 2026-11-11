"use client";

import { Fragment, useState } from "react";
import { ChevronDown, Pencil, Plus, ShieldCheck, Trash2, Users as UsersIcon } from "lucide-react";

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
import type { Category } from "@/types/category";

const PERMS = ["can_view", "can_execute", "can_create", "can_edit", "can_delete", "can_approve"] as const;
type Perm = (typeof PERMS)[number];

const emptyForm = { name: "", email: "", password: "", role_id: "", is_active: true };

export function UsersManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const users = useApi<User[]>("/users");
  const roles = useApi<Role[]>("/roles");
  const categories = useApi<Category[]>("/categories");

  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [draft, setDraft] = useState<User[] | null>(null);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState(emptyForm);

  const list = draft ?? users.data ?? [];

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setModalOpen(true);
  }

  function openEdit(user: User) {
    setEditing(user);
    setForm({
      name: user.name,
      email: user.email,
      password: "",
      role_id: String(user.role.id),
      is_active: user.is_active,
    });
    setModalOpen(true);
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
        ...(editing || form.password ? { password: form.password || null } : { password: form.password }),
      };
      await apiRequest<User>(editing ? `/users/${editing.id}` : "/users", {
        method: editing ? "PUT" : "POST",
        token,
        body: JSON.stringify(body),
      });
      toast({ title: editing ? "Usuário atualizado" : "Usuário criado", kind: "success" });
      setForm(emptyForm);
      setEditing(null);
      setModalOpen(false);
      await users.refetch();
      setDraft(null);
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  async function removeUser(user: User) {
    if (!token) return;
    if (!window.confirm(`Apagar o usuário "${user.name}"?`)) return;
    try {
      await apiRequest<void>(`/users/${user.id}`, { method: "DELETE", token });
      toast({ title: "Usuário apagado", kind: "success" });
      await users.refetch();
      setDraft(null);
    } catch (err) {
      toast({ title: "Falha ao apagar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  function toggle(userId: number, categoryId: number, field: Perm) {
    setDraft((prev) => {
      const base = prev ?? users.data ?? [];
      return base.map((u) => {
        if (u.id !== userId) return u;
        const existing = u.category_permissions.find((p) => p.category_id === categoryId);
        if (existing) {
          return {
            ...u,
            category_permissions: u.category_permissions.map((p) =>
              p.category_id === categoryId ? { ...p, [field]: !p[field] } : p,
            ),
          };
        }
        return {
          ...u,
          category_permissions: [
            ...u.category_permissions,
            {
              category_id: categoryId,
              can_view: field === "can_view",
              can_execute: field === "can_execute",
              can_create: field === "can_create",
              can_edit: field === "can_edit",
              can_delete: field === "can_delete",
              can_approve: field === "can_approve",
            },
          ],
        };
      });
    });
  }

  async function savePermissions(user: User) {
    if (!token) return;
    try {
      await apiRequest<User>(`/users/${user.id}/permissions`, {
        method: "PUT",
        token,
        body: JSON.stringify({
          permissions: (categories.data ?? []).map((c) => {
            const p = user.category_permissions.find((x) => x.category_id === c.id);
            return {
              category_id: c.id,
              can_view: p?.can_view ?? false,
              can_execute: p?.can_execute ?? false,
              can_create: p?.can_create ?? false,
              can_edit: p?.can_edit ?? false,
              can_delete: p?.can_delete ?? false,
              can_approve: p?.can_approve ?? false,
            };
          }),
        }),
      });
      toast({ title: "Permissões salvas", kind: "success" });
      await users.refetch();
      setDraft(null);
    } catch (err) {
      toast({ title: "Falha ao salvar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Novo usuario
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
                      <Badge tone={user.is_active ? "success" : "neutral"}>{user.is_active ? "Ativo" : "Inativo"}</Badge>
                    </TD>
                    <TD>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setExpanded(expanded === user.id ? null : user.id)}
                          title="Permissões"
                        >
                          <ShieldCheck className="h-4 w-4" />
                          <ChevronDown className={cn("h-3 w-3 transition-transform", expanded === user.id && "rotate-180")} />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => openEdit(user)} title="Editar usuário">
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
                      <TD colSpan={5} className="bg-muted/30">
                        <div className="space-y-3 py-1">
                          {(categories.data ?? []).map((category) => {
                            const perm = user.category_permissions.find((p) => p.category_id === category.id);
                            return (
                              <div key={category.id} className="rounded-md border border-border bg-card p-3">
                                <p className="text-sm font-medium">{category.name}</p>
                                <div className="mt-2 flex flex-wrap gap-3">
                                  {PERMS.map((field) => (
                                    <label key={field} className="flex items-center gap-1.5 text-xs">
                                      <input
                                        type="checkbox"
                                        checked={perm?.[field] ?? false}
                                        onChange={() => toggle(user.id, category.id, field)}
                                        className="h-3.5 w-3.5 accent-primary"
                                      />
                                      {field.replace("can_", "")}
                                    </label>
                                  ))}
                                </div>
                              </div>
                            );
                          })}
                          <div className="flex justify-end">
                            <Button size="sm" onClick={() => savePermissions(user)}>
                              Salvar permissões
                            </Button>
                          </div>
                        </div>
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
              disabled={submitting || !form.name || !form.email || !form.role_id || (!editing && !form.password)}
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
          <Field>
            <Label htmlFor="u-pass">{editing ? "Nova senha (opcional)" : "Senha inicial"}</Label>
            <Input id="u-pass" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field>
          <Field>
            <Label htmlFor="u-role">Papel</Label>
            <Select id="u-role" value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
              <option value="">Selecione...</option>
              {roles.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="h-4 w-4 accent-primary"
            />
            Usuario ativo
          </label>
        </div>
      </Modal>
    </div>
  );
}
