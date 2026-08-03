"use client";

import { useState } from "react";
import { CheckCircle2, FlaskConical, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, Label, Textarea } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type { Trigger, TriggerDryRunResult } from "@/types/trigger";

function parseJson(value: string, label: string): Record<string, unknown> {
  const parsed = value.trim() ? JSON.parse(value) : {};
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label} deve ser um objeto JSON.`);
  return parsed as Record<string, unknown>;
}

export function WebhookTestPanel({ trigger, open, onClose }: { trigger: Trigger | null; open: boolean; onClose: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [payload, setPayload] = useState('{\n  "company_id": 123\n}');
  const [headers, setHeaders] = useState('{\n  "x-customer": "cliente-a"\n}');
  const [query, setQuery] = useState('{\n  "force": "true"\n}');
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TriggerDryRunResult | null>(null);

  async function run() {
    if (!token || !trigger) return;
    let samplePayload: Record<string, unknown>;
    let sampleHeaders: Record<string, unknown>;
    let sampleQuery: Record<string, unknown>;
    try {
      samplePayload = parseJson(payload, "Payload");
      sampleHeaders = parseJson(headers, "Headers");
      sampleQuery = parseJson(query, "Query parameters");
    } catch (err) {
      toast({ title: "JSON invalido", description: err instanceof Error ? err.message : undefined, kind: "error" });
      return;
    }
    setTesting(true);
    setResult(null);
    try {
      const response = await apiRequest<TriggerDryRunResult>(`/triggers/${trigger.id}/test`, {
        method: "POST",
        token,
        body: JSON.stringify({
          sample_payload: samplePayload,
          sample_headers: sampleHeaders,
          sample_query_params: sampleQuery,
        }),
      });
      setResult(response);
    } catch (err) {
      toast({ title: "Falha no teste", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setTesting(false);
    }
  }

  return (
    <Sheet
      open={open && !!trigger}
      onClose={onClose}
      title="Teste de mapeamento"
      description={trigger ? `${trigger.method || "POST"} /${trigger.route_path}` : "Valide payload, headers e query params."}
      widthClassName="w-full sm:max-w-5xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Fechar
          </Button>
          <Button onClick={run} disabled={testing || !trigger}>
            {testing && <Spinner />} Testar
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="rounded-md border border-info/30 bg-info/5 p-3 text-sm text-info">
          <FlaskConical className="mr-2 inline h-4 w-4" /> Nenhuma execução é criada neste dry-run. O backend só aplica o mapping e retorna os parâmetros que seriam enviados.
        </div>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
          <div className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-3">
              <Field>
                <Label>Payload</Label>
                <Textarea rows={10} className="tabular min-h-[220px] font-mono text-xs" value={payload} onChange={(event) => setPayload(event.target.value)} />
              </Field>
              <Field>
                <Label>Headers</Label>
                <Textarea rows={10} className="tabular min-h-[220px] font-mono text-xs" value={headers} onChange={(event) => setHeaders(event.target.value)} />
              </Field>
              <Field>
                <Label>Query params</Label>
                <Textarea rows={10} className="tabular min-h-[220px] font-mono text-xs" value={query} onChange={(event) => setQuery(event.target.value)} />
              </Field>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2">
              {result?.valid ? <CheckCircle2 className="h-4 w-4 text-success" /> : result ? <XCircle className="h-4 w-4 text-destructive" /> : <FlaskConical className="h-4 w-4 text-muted-foreground" />}
              <h3 className="font-display text-sm font-semibold tracking-tight">
                {result ? (result.valid ? "Mapping válido" : "Mapping com pendências") : "Resultado do dry-run"}
              </h3>
            </div>
            {!result ? (
              <p className="mt-3 text-sm text-muted-foreground">Execute o teste para ver os parâmetros normalizados que a automação receberia.</p>
            ) : (
              <>
                {result.errors.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs text-destructive">
                    {result.errors.map((error) => (
                      <li key={error}>{error}</li>
                    ))}
                  </ul>
                )}
                <pre className="tabular mt-3 max-h-[420px] overflow-auto rounded-md border border-border bg-background p-3 text-xs">
                  {JSON.stringify(result.parameters, null, 2)}
                </pre>
              </>
            )}
          </div>
        </div>
      </div>
    </Sheet>
  );
}
