"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select, Textarea, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { priorityScoreFromLabel } from "@/lib/status";
import type { Automation } from "@/types/automation";
import type { Execution } from "@/types/execution";

const PRIORITIES = ["critical", "high", "normal", "low"];

type AutomationVersion = {
  id: number;
  automation_id: number;
  version: string;
  status: string;
  published_at: string | null;
};

export function DispatchDialog({
  open,
  onClose,
  automations,
  onDispatched,
}: {
  open: boolean;
  onClose: () => void;
  automations: Automation[];
  onDispatched: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [automationId, setAutomationId] = useState("");
  const [priority, setPriority] = useState("normal");
  const [payload, setPayload] = useState('{\n  "source": "portal-ui"\n}');
  const [submitting, setSubmitting] = useState(false);
  const [payloadError, setPayloadError] = useState<string | null>(null);

  async function dispatch() {
    if (!token || !automationId) return;
    let parsed: Record<string, unknown> = {};
    if (payload.trim()) {
      try {
        parsed = JSON.parse(payload);
      } catch {
        setPayloadError("JSON inválido");
        return;
      }
    }
    setPayloadError(null);
    setSubmitting(true);
    try {
      // /executions requires a specific automation_version_id (an Execution
      // is always tied to one published version) — resolve the latest
      // published version of the chosen automation first, same as the old
      // JobDispatcherService did server-side via get_latest_published_version.
      const versions = await apiRequest<AutomationVersion[]>(`/automations/${automationId}/versions`, { token });
      const published = versions
        .filter((v) => v.status === "published")
        .sort((a, b) => new Date(b.published_at ?? 0).getTime() - new Date(a.published_at ?? 0).getTime());
      const version = published[0];
      if (!version) {
        toast({ title: "Falha ao despachar", description: "Esta automação não tem versão publicada.", kind: "error" });
        return;
      }
      await apiRequest<Execution>("/executions", {
        method: "POST",
        token,
        body: JSON.stringify({
          automation_version_id: version.id,
          priority: priorityScoreFromLabel(priority),
          parameters: parsed,
        }),
      });
      toast({ title: "Job despachado", kind: "success" });
      onClose();
      onDispatched();
    } catch (err) {
      toast({ title: "Falha ao despachar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Disparar job"
      description="Cria um job manual para a automação selecionada."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
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
          <Label htmlFor="d-automation">Automação</Label>
          <Select id="d-automation" value={automationId} onChange={(e) => setAutomationId(e.target.value)}>
            <option value="">Selecione…</option>
            {automations.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field>
          <Label htmlFor="d-priority">Prioridade</Label>
          <Select id="d-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
        <Field>
          <Label htmlFor="d-payload">Payload (JSON)</Label>
          <Textarea
            id="d-payload"
            className="tabular min-h-[120px]"
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
          />
          {payloadError && <p className="text-xs text-destructive">{payloadError}</p>}
        </Field>
      </div>
    </Modal>
  );
}
