"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select, Textarea, Label, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Automation } from "@/types/automation";
import type { Job } from "@/types/job";

const PRIORITIES = ["critical", "high", "normal", "low"];

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
      await apiRequest<Job>("/jobs", {
        method: "POST",
        token,
        body: JSON.stringify({ automation_id: Number(automationId), priority, payload_json: parsed }),
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
