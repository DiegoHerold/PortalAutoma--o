"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Label, Select, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { priorityScoreFromLabel } from "@/lib/status";
import type { Automation } from "@/types/automation";
import type { AutomationVersionResponse } from "@/types/catalog";
import type { Execution, ExecutionDetails } from "@/types/execution";

const PRIORITIES = ["critical", "high", "normal", "low"];

export function TriggerJobDialog({
  open,
  onClose,
  automations,
  onDispatched,
}: {
  open: boolean;
  onClose: () => void;
  automations: Automation[];
  onDispatched: (execution: Execution) => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [automationId, setAutomationId] = useState("");
  const [priority, setPriority] = useState("normal");
  const [payload, setPayload] = useState('{\n  "source": "portal-ui"\n}');
  const [submitting, setSubmitting] = useState(false);
  const [payloadError, setPayloadError] = useState<string | null>(null);

  async function dispatch() {
    if (!token || !automationId || submitting) return;
    let parsed: Record<string, unknown> = {};
    if (payload.trim()) {
      try {
        parsed = JSON.parse(payload) as Record<string, unknown>;
      } catch {
        setPayloadError("JSON inválido");
        return;
      }
    }

    setPayloadError(null);
    setSubmitting(true);
    try {
      const versions = await apiRequest<AutomationVersionResponse[]>(`/automations/${automationId}/versions`, { token });
      const version = versions
        .filter((item) => item.status === "published")
        .sort((a, b) => new Date(b.published_at ?? 0).getTime() - new Date(a.published_at ?? 0).getTime())[0];

      if (!version) {
        toast({ title: "Falha ao disparar", description: "Esta automação não tem versão publicada.", kind: "error" });
        return;
      }

      const created = await apiRequest<ExecutionDetails>("/executions", {
        method: "POST",
        token,
        body: JSON.stringify({
          automation_version_id: version.id,
          priority: priorityScoreFromLabel(priority),
          parameters: parsed,
        }),
      });

      toast({ title: "Job disparado", description: `Execução #${created.execution.id} criada.`, kind: "success" });
      onDispatched(created.execution);
      onClose();
    } catch (err) {
      toast({ title: "Falha ao disparar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Disparar job"
      description="Cria uma execução manual para a automação selecionada."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button onClick={dispatch} disabled={submitting || !automationId}>
            {submitting && <Spinner />} Disparar
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field>
          <Label htmlFor="execution-automation">Automação</Label>
          <Select id="execution-automation" value={automationId} onChange={(event) => setAutomationId(event.target.value)}>
            <option value="">Selecione...</option>
            {automations.map((automation) => (
              <option key={automation.id} value={automation.id}>
                {automation.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field>
          <Label htmlFor="execution-priority">Prioridade</Label>
          <Select id="execution-priority" value={priority} onChange={(event) => setPriority(event.target.value)}>
            {PRIORITIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
        </Field>

        <Field>
          <Label htmlFor="execution-payload">Payload (JSON)</Label>
          <Textarea
            id="execution-payload"
            className="tabular min-h-[120px]"
            value={payload}
            onChange={(event) => setPayload(event.target.value)}
          />
          {payloadError && <p className="text-xs text-destructive">{payloadError}</p>}
        </Field>
      </div>
    </Modal>
  );
}
