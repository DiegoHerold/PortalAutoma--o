"use client";

import { useEffect, useState } from "react";

import { WebhookMappingEditor } from "@/components/webhooks/webhook-mapping-editor";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import type { Automation } from "@/types/automation";
import type { Trigger } from "@/types/trigger";

import { triggerToPayload, type WebhookPayload } from "./webhook-utils";

const ROUTE_RE = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$/;
const RESERVED_PREFIXES = new Set(["api", "github", "invoke", "trigger", "webhooks"]);

type FormState = WebhookPayload;

function emptyState(automations: Automation[]): FormState {
  return {
    name: "",
    automation_id: automations[0]?.id ?? 0,
    trigger_type: "https",
    route_path: "",
    is_active: true,
    parameter_mapping_json: null,
  };
}

function validationError(state: FormState, existing: Trigger[], editingId?: number | null): string | null {
  if (!state.automation_id) return "Selecione a automacao de destino.";
  const routePath = state.route_path.trim().replace(/^\/+|\/+$/g, "");
  if (!routePath) return "Informe o route path.";
  if (/\s/.test(routePath) || routePath.includes("\\") || routePath.includes("//") || routePath.includes("..")) {
    return "O route path nao pode conter espacos, barras duplicadas, barra invertida ou '..'.";
  }
  if (!ROUTE_RE.test(routePath)) return "Use apenas letras, numeros, ponto, traco, underscore e barras simples.";
  if (RESERVED_PREFIXES.has(routePath.split("/", 1)[0])) return "Este prefixo de route path e reservado.";
  const duplicated = existing.some((trigger) => trigger.id !== editingId && trigger.trigger_type === "https" && trigger.route_path === routePath);
  if (duplicated) return "Ja existe um Webhook com este route path.";
  return null;
}

export function WebhookForm({
  open,
  onClose,
  automations,
  existing,
  editing,
  onSubmit,
  submitting,
}: {
  open: boolean;
  onClose: () => void;
  automations: Automation[];
  existing: Trigger[];
  editing: Trigger | null;
  onSubmit: (payload: WebhookPayload, editing: Trigger | null) => Promise<void>;
  submitting: boolean;
}) {
  const [state, setState] = useState<FormState>(() => (editing ? triggerToPayload(editing) : emptyState(automations)));

  useEffect(() => {
    if (!open) return;
    setState(editing ? triggerToPayload(editing) : emptyState(automations));
  }, [automations, editing, open]);

  const error = validationError(state, existing, editing?.id);

  async function save() {
    if (error) return;
    await onSubmit({ ...state, route_path: state.route_path.trim().replace(/^\/+|\/+$/g, ""), name: state.name?.trim() || null }, editing);
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={editing ? "Editar Webhook" : "Novo Webhook"}
      description="Webhook HTTP de entrada para disparar uma automacao publicada."
      widthClassName="w-full sm:max-w-2xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={save} disabled={submitting || !!error}>
            {submitting && <Spinner />} {editing ? "Salvar" : "Criar"}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <Field>
          <Label htmlFor="webhook-name">Nome</Label>
          <Input
            id="webhook-name"
            placeholder="N8N - cadastro de cliente"
            value={state.name ?? ""}
            onChange={(event) => setState((value) => ({ ...value, name: event.target.value }))}
          />
        </Field>
        <Field>
          <Label htmlFor="webhook-automation">Automacao de destino</Label>
          <Select
            id="webhook-automation"
            value={state.automation_id || ""}
            onChange={(event) => setState((value) => ({ ...value, automation_id: Number(event.target.value) }))}
          >
            <option value="">Selecione...</option>
            {automations.map((automation) => (
              <option key={automation.id} value={automation.id}>
                {automation.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field>
          <Label htmlFor="webhook-route">Route path</Label>
          <Input
            id="webhook-route"
            className="tabular"
            placeholder="clientes/novo"
            value={state.route_path}
            onChange={(event) => setState((value) => ({ ...value, route_path: event.target.value }))}
          />
          <p className="text-xs text-muted-foreground">Sem espacos. Pode usar letras, numeros, ponto, traco, underscore e barras simples.</p>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={state.is_active}
            onChange={(event) => setState((value) => ({ ...value, is_active: event.target.checked }))}
            className="h-4 w-4 accent-primary"
          />
          Ativo para novas invocacoes
        </label>
        <WebhookMappingEditor
          key={editing?.id ?? "new"}
          value={state.parameter_mapping_json}
          onChange={(mapping) => setState((value) => ({ ...value, parameter_mapping_json: mapping }))}
        />
        <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
          O backend gera o secret na criacao. Edicoes comuns nao reenviam secret antigo; use rotacao para trocar credenciais.
        </div>
        {error && <p className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</p>}
      </div>
    </Sheet>
  );
}
