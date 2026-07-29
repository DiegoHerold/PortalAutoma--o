"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Play } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { createFlowExecution } from "@/lib/flow-api";
import type { Flow, FlowVersion } from "@/types/flow";

type SchemaProperty = { type?: string; description?: string; default?: unknown };

function schemaProperties(schema: Record<string, unknown> | null): Record<string, SchemaProperty> {
  if (!schema || typeof schema !== "object") return {};
  const props = (schema as { properties?: unknown }).properties;
  if (!props || typeof props !== "object") return {};
  return props as Record<string, SchemaProperty>;
}

export function RunFlowDialog({
  flow,
  versions,
  open,
  onClose,
}: {
  flow: Flow | null;
  versions: FlowVersion[];
  open: boolean;
  onClose: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [versionId, setVersionId] = useState<string>("");
  const [simpleValues, setSimpleValues] = useState<Record<string, string>>({});
  const [rawJson, setRawJson] = useState("{}");
  const [mode, setMode] = useState<"simple" | "json">("simple");

  const published = useMemo(() => versions.filter((v) => v.status === "published"), [versions]);
  const selected = published.find((v) => v.id === versionId) ?? published[0] ?? null;
  const properties = useMemo(() => schemaProperties(selected?.input_schema ?? null), [selected]);
  const hasSchema = Object.keys(properties).length > 0;

  if (!open || !flow) return null;

  async function run() {
    if (!token || !selected) return;
    setSubmitting(true);
    try {
      let input: Record<string, unknown> = {};
      if (mode === "simple" && hasSchema) {
        input = Object.fromEntries(Object.entries(simpleValues).filter(([, v]) => v !== ""));
      } else {
        try {
          input = rawJson.trim() ? JSON.parse(rawJson) : {};
        } catch {
          toast({ title: "JSON de entrada inválido", kind: "error" });
          setSubmitting(false);
          return;
        }
      }
      const details = await createFlowExecution(token, { flow_version_id: selected.id, input, origin: "manual" });
      toast({ title: "Execução iniciada", kind: "success" });
      onClose();
      router.push(`/flow-executions/${details.flow_execution.id}`);
    } catch (err) {
      toast({ title: "Falha ao executar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Executar "${flow.name}"`}
      description={published.length === 0 ? "Este Fluxo ainda não tem nenhuma versão publicada." : "Informe os dados de entrada e inicie a execução."}
      footer={
        published.length > 0 && (
          <>
            <Button variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button onClick={run} disabled={submitting || !selected}>
              <Play className="h-4 w-4" /> {submitting ? "Iniciando..." : "Executar"}
            </Button>
          </>
        )
      }
    >
      {published.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Publique uma versão no editor do Fluxo antes de executar.
        </p>
      ) : (
        <div className="space-y-4">
          {published.length > 1 && (
            <Field>
              <Label htmlFor="run-version">Versão publicada</Label>
              <Select id="run-version" value={selected?.id ?? ""} onChange={(e) => setVersionId(e.target.value)}>
                {published.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {hasSchema ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Entrada</Label>
                <button type="button" className="text-xs text-primary underline underline-offset-2" onClick={() => setMode(mode === "simple" ? "json" : "simple")}>
                  {mode === "simple" ? "Editar como JSON" : "Usar campos simples"}
                </button>
              </div>
              {mode === "simple" ? (
                Object.entries(properties).map(([field, prop]) => (
                  <Field key={field}>
                    <Label htmlFor={`prop-${field}`}>{field}</Label>
                    <Input
                      id={`prop-${field}`}
                      placeholder={prop.description ?? (prop.default !== undefined ? String(prop.default) : undefined)}
                      value={simpleValues[field] ?? ""}
                      onChange={(e) => setSimpleValues((prev) => ({ ...prev, [field]: e.target.value }))}
                    />
                    {prop.description && <p className="text-xs text-muted-foreground">{prop.description}</p>}
                  </Field>
                ))
              ) : (
                <Textarea rows={8} className="font-mono text-xs" value={rawJson} onChange={(e) => setRawJson(e.target.value)} />
              )}
            </div>
          ) : (
            <Field>
              <Label htmlFor="run-json">Entrada (JSON)</Label>
              <Textarea id="run-json" rows={8} className="font-mono text-xs" value={rawJson} onChange={(e) => setRawJson(e.target.value)} />
              <p className="text-xs text-muted-foreground">Este Fluxo não define um input_schema — informe o JSON diretamente.</p>
            </Field>
          )}
        </div>
      )}
    </Modal>
  );
}
