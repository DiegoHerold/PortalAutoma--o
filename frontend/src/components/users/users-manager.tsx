"use client";

import type { FormEvent } from "react";
import { Fragment } from "react";
import { useEffect, useState } from "react";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Category } from "@/types/category";
import type { Role } from "@/types/role";
import type { User } from "@/types/user";

type UserFormState = {
  name: string;
  email: string;
  password: string;
  role_id: string;
  is_active: boolean;
};

type PermissionField =
  | "can_view"
  | "can_execute"
  | "can_create"
  | "can_edit"
  | "can_delete"
  | "can_approve";

const initialForm: UserFormState = {
  name: "",
  email: "",
  password: "",
  role_id: "",
  is_active: true,
};

export function UsersManager() {
  const { token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<UserFormState>(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  async function load() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [usersData, rolesData, categoriesData] = await Promise.all([
        apiRequest<User[]>("/users", { token }),
        apiRequest<Role[]>("/roles", { token }),
        apiRequest<Category[]>("/categories", { token }),
      ]);
      setUsers(usersData);
      setRoles(rolesData);
      setCategories(categoriesData);
      if (!form.role_id && rolesData[0]) {
        setForm((current) => ({ ...current, role_id: String(rolesData[0].id) }));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao carregar usuarios.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    if (!form.role_id) {
      setError("Selecione um papel antes de criar o usuario.");
      return;
    }
    setError(null);
    await apiRequest<User>("/users", {
      method: "POST",
      token,
      body: JSON.stringify({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        role_id: Number(form.role_id),
        is_active: form.is_active,
      }),
    });
    setForm(initialForm);
    await load();
  }

  async function savePermissions(user: User) {
    if (!token) return;
    await apiRequest<User>(`/users/${user.id}/permissions`, {
      method: "PUT",
      token,
      body: JSON.stringify({
        permissions: categories.map((category) => {
          const existing = user.category_permissions.find(
            (permission) => permission.category_id === category.id,
          );
          return {
            category_id: category.id,
            can_view: existing?.can_view ?? false,
            can_execute: existing?.can_execute ?? false,
            can_create: existing?.can_create ?? false,
            can_edit: existing?.can_edit ?? false,
            can_delete: existing?.can_delete ?? false,
            can_approve: existing?.can_approve ?? false,
          };
        }),
      }),
    });
    await load();
  }

  function togglePermission(
    userId: number,
    categoryId: number,
    field: PermissionField,
  ) {
    setUsers((current) =>
      current.map((user) => {
        if (user.id !== userId) return user;
        const existing = user.category_permissions.find((permission) => permission.category_id === categoryId);
        if (existing) {
          return {
            ...user,
            category_permissions: user.category_permissions.map((permission) =>
              permission.category_id === categoryId
                ? { ...permission, [field]: !permission[field] }
                : permission,
            ),
          };
        }
        return {
          ...user,
          category_permissions: [
            ...user.category_permissions,
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
      }),
    );
  }

  if (loading) return <LoadingState label="Carregando usuarios..." />;

  return (
    <div className="space-y-6">
      <form className="grid gap-3 rounded-3xl bg-white/80 p-6 shadow-sm md:grid-cols-2" onSubmit={handleSubmit}>
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="Nome" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="E-mail" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        <input className="rounded-2xl border border-slate-200 px-4 py-3" placeholder="Senha inicial" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        <select className="rounded-2xl border border-slate-200 px-4 py-3" value={form.role_id} onChange={(event) => setForm({ ...form, role_id: event.target.value })}>
          <option value="">Selecione um papel</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
          Usuario ativo
        </label>
        <button className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white disabled:opacity-60" type="submit" disabled={!form.name.trim() || !form.email.trim() || !form.password || !form.role_id}>
          Criar usuario
        </button>
      </form>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white/80 shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-3">Nome</th>
              <th className="px-4 py-3">E-mail</th>
              <th className="px-4 py-3">Papel</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <Fragment key={user.id}>
                <tr key={user.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{user.name}</td>
                  <td className="px-4 py-3">{user.email}</td>
                  <td className="px-4 py-3">{user.role.name}</td>
                  <td className="px-4 py-3">{user.is_active ? "Ativo" : "Inativo"}</td>
                  <td className="px-4 py-3 text-right">
                    <button className="text-accent" type="button" onClick={() => setSelectedUserId(selectedUserId === user.id ? null : user.id)}>
                      {selectedUserId === user.id ? "Fechar permissoes" : "Editar permissoes"}
                    </button>
                  </td>
                </tr>
                {selectedUserId === user.id ? (
                  <tr className="border-t border-slate-100 bg-slate-50/70">
                    <td className="px-4 py-4" colSpan={5}>
                      <div className="space-y-4">
                        {categories.map((category) => {
                          const permission = user.category_permissions.find(
                            (item) => item.category_id === category.id,
                          );
                          const checks = [
                            "can_view",
                            "can_execute",
                            "can_create",
                            "can_edit",
                            "can_delete",
                            "can_approve",
                          ] as const;
                          return (
                            <div key={category.id} className="rounded-2xl bg-white p-4">
                              <p className="font-semibold">{category.name}</p>
                              <div className="mt-3 flex flex-wrap gap-4 text-sm">
                                {checks.map((field) => (
                                  <label key={field} className="flex items-center gap-2">
                                    <input
                                      type="checkbox"
                                      checked={permission?.[field] ?? false}
                                      onChange={() => togglePermission(user.id, category.id, field)}
                                    />
                                    {field.replace("can_", "")}
                                  </label>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                        <button className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white" type="button" onClick={() => void savePermissions(user)}>
                          Salvar permissoes
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
