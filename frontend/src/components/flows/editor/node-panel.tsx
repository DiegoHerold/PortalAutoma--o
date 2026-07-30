"use client";

import { useEffect, useState } from "react";
import { Trash2, AlertTriangle } from "lucide-react";

import { Sheet } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Label, Select, Textarea } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { ConditionEditor } from "@/components/flows/editor/condition-editor";
import { MappingEditor } from "@/components/flows/editor/mapping-editor";
import type { FlowCanvasNode } from "@/components/flows/editor/types";
import type { Automation } from "@/types/automation";
import type { AutomationVersionResponse as AutomationVersion } from "@/types/catalog";
import type { FlowFailurePolicy } from "@/types/flow";

export type NodeConfigPatch = {
  name?: string;
  automation_version_id?: number | null;
  input_mapping?: Record<string, unknown>;
  output_mapping?: Record<string, unknown>;
  condition?: Record<string, unknown> | null;
  retry_policy?: Record<string, unknown>;
  timeout_policy?: Record<string, unknown>;
  failure_policy?: FlowFailurePolicy;
  execution_policy?: Record<string, unknown>;
  configuration?: Record<string, unknown>;
};

export function NodePanel({
  node,
  upstreamNodes,
  automations,
  automationVersions,
  onLoadAutomationVersions,
  readOnly,
  onClose,
  onSave,
  onDelete,
  onDuplicate,
}: {
  node: FlowCanvasNode | null;
  upstreamNodes: { key: string; name: string }[];
  automations: Automation[];
  automationVersions: AutomationVersion[];
  onLoadAutomationVersions: (automationId: number) => void;
  readOnly: boolean;
  onClose: () => void;
  onSave: (patch: NodeConfigPatch) => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const [tab, setTab] = useState("config");
  const [name, setName] = useState("");
  const [automationId, setAutomationId] = useState<string>("");
  const [automationVersionId, setAutomationVersionId] = useState<string>("");
  const [inputMapping, setInputMapping] = useState<Record<string, unknown>>({});
  const [outputMapping, setOutputMapping] = useState<Record<string, unknown>>({});
  const [condition, setCondition] = useState<Record<string, unknown> | null>(null);
  const [conditionEnabled, setConditionEnabled] = useState(false);
  const [maxAttempts, setMaxAttempts] = useState("1");
  const [maxRetries, setMaxRetries] = useState("0");
  const [timeoutSeconds, setTimeoutSeconds] = useState("");
  const [dependencyPolicy, setDependencyPolicy] = useState("all");
  const [failurePolicy, setFailurePolicy] = useState<FlowFailurePolicy>("fail_flow");
  const [configJson, setConfigJson] = useState("{}");

  useEffect(() => {
    if (!node) return;
    const fn = node.data.flowNode;
    setTab("config");
    setName(fn.name || "");
    setAutomationVersionId(fn.automation_version_id ? String(fn.automation_version_id) : "");
    setInputMapping(fn.input_mapping || {});
    setOutputMapping(fn.output_mapping || {});
    setConditionEnabled(Boolean(fn.condition));
    setCondition(fn.condition ?? null);
    setMaxAttempts(String((fn.retry_policy as Record<string, unknown> | undefined)?.max_attempts ?? 1));
    setMaxRetries(String((fn.retry_policy as Record<string, unknown> | undefined)?.max_retries ?? 0));
    setTimeoutSeconds(String((fn.timeout_policy as Record<string, unknown> | undefined)?.execution_timeout_seconds ?? ""));
    setDependencyPolicy(String((fn.execution_policy as Record<string, unknown> | undefined)?.dependency_policy ?? "all"));
    setFailurePolicy(fn.failure_policy);
    setConfigJson(JSON.stringify(fn.configuration || {}, null, 2));
  }, [node]);

  useEffect(() => {
    if (!node) return;
    const fn = node.data.flowNode;
    if (fn.node_type !== "automation" || !fn.automation_version_id) {
      setAutomationId("");
      return;
    }
    const match = automationVersions.find((v) => v.id === fn.automation_version_id);
    if (match) setAutomationId(String(match.automation_id));
  }, [node, automationVersions]);

  if (!node) return null;
  const fn = node.data.flowNode;
  const allVersionsForAutomation = automationId ? automationVersions.filter((v) => v.automation_id === Number(automationId)) : [];
  const versionsForAutomation = allVersionsForAutomation.filter((v) => v.status === "published");
  const nonPublishedCount = allVersionsForAutomation.length - versionsForAutomation.length;

  function save() {
    let configuration: Record<string, unknown> = {};
    try {
      configuration = JSON.parse(configJson);
    } catch {
      // ignora config inválida, mantém {}
    }
    onSave({
      name,
      automation_version_id: automationVersionId ? Number(automationVersionId) : null,
      input_mapping: inputMapping,
      output_mapping: outputMapping,
      condition: conditionEnabled ? condition : null,
      retry_policy: { max_attempts: Number(maxAttempts) || 1, max_retries: Number(maxRetries) || 0 },
      timeout_policy: timeoutSeconds ? { execution_timeout_seconds: Number(timeoutSeconds) } : {},
      failure_policy: failurePolicy,
      execution_policy: { dependency_policy: dependencyPolicy },
      configuration,
    });
  }

  const nodeIssues = node.data.issues;

  return (
    <Sheet
      open={Boolean(node)}
      onClose={onClose}
      title={fn.name || fn.key}
      description={`${fn.node_type} · ${fn.key}`}
      widthClassName="w-full sm:max-w-2xl"
      footer={
        !readOnly && (
          <>
            <Button variant="outline" className="mr-auto text-destructive hover:bg-destructive/10" onClick={onDelete}>
              <Trash2 className="h-4 w-4" /> Remover nó
            </Button>
            <Button variant="outline" onClick={onDuplicate}>
              Duplicar
            </Button>
            <Button onClick={save}>Salvar</Button>
          </>
        )
      }
    >
      <div className="space-y-4">
        {nodeIssues.length > 0 && (
          <div className="space-y-1.5 rounded-md border border-destructive/30 bg-destructive/5 p-3">
            {nodeIssues.map((issue, i) => (
              <p key={i} className="flex items-start gap-1.5 text-xs text-destructive">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {issue.message}
              </p>
            ))}
          </div>
        )}

        <Tabs
          value={tab}
          onValueChange={setTab}
          items={[
            { value: "config", label: "Configuração" },
            { value: "mappings", label: "Mapeamentos" },
            { value: "condition", label: "Condição" },
            { value: "retry", label: "Retry & Timeout" },
            { value: "failure", label: "Falha" },
          ]}
        />

        {tab === "config" && (
          <div className="space-y-4">
            <Field>
              <Label htmlFor="node-name">Nome</Label>
              <Input id="node-name" value={name} disabled={readOnly} onChange={(e) => setName(e.target.value)} />
            </Field>

            {fn.node_type === "automation" && (
              <>
                <Field>
                  <Label htmlFor="node-automation">Automação</Label>
                  <Select
                    id="node-automation"
                    value={automationId}
                    disabled={readOnly}
                    onChange={(e) => {
                      setAutomationId(e.target.value);
                      setAutomationVersionId("");
                      if (e.target.value) onLoadAutomationVersions(Number(e.target.value));
                    }}
                  >
                    <option value="">Selecione...</option>
                    {automations.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </Select>
                  {automations.length === 0 && (
                    <p className="text-xs text-warning">
                      Nenhuma automação encontrada. Cadastre e importe um pacote em Automações antes de montar o Fluxo.
                    </p>
                  )}
                </Field>
                <Field>
                  <Label htmlFor="node-automation-version">Versão publicada</Label>
                  <Select id="node-automation-version" value={automationVersionId} disabled={readOnly || !automationId} onChange={(e) => setAutomationVersionId(e.target.value)}>
                    <option value="">Selecione...</option>
                    {versionsForAutomation.map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.version}
                      </option>
                    ))}
                  </Select>
                  {automationId && versionsForAutomation.length === 0 && (
                    <p className="text-xs text-warning">
                      {nonPublishedCount > 0
                        ? `Esta automação tem ${nonPublishedCount} versão(ões), mas nenhuma publicada. Só é possível usar num Fluxo uma versão publicada — abra a automação em Automações e clique em "Publicar".`
                        : "Esta automação ainda não tem nenhuma versão importada."}
                    </p>
                  )}
                </Field>
              </>
            )}

            <Field>
              <Label htmlFor="node-config">Configuração avançada (JSON)</Label>
              <Textarea id="node-config" rows={6} className="font-mono text-xs" disabled={readOnly} value={configJson} onChange={(e) => setConfigJson(e.target.value)} />
              <p className="text-xs text-muted-foreground">
                Opcional. Só use se a automação precisar de parâmetros extras fixos que não vêm do mapeamento de entrada.
              </p>
            </Field>
          </div>
        )}

        {tab === "mappings" && (
          <div className="space-y-6">
            <MappingEditor
              title="Inputs (entrada da automação)"
              description="De onde vem cada campo que a automação deste nó vai receber."
              mapping={inputMapping}
              upstreamNodes={upstreamNodes}
              onChange={setInputMapping}
              readOnly={readOnly}
            />
            <div className="border-t border-border pt-4">
              <MappingEditor
                title="Outputs (saída do nó)"
                description="Como montar a saída deste nó a partir do resultado da automação — opcional."
                mapping={outputMapping}
                upstreamNodes={upstreamNodes}
                onChange={setOutputMapping}
                readOnly={readOnly}
              />
            </div>
          </div>
        )}

        {tab === "condition" && (
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={conditionEnabled} disabled={readOnly} onChange={(e) => setConditionEnabled(e.target.checked)} />
              Só executar este nó se a condição abaixo for verdadeira
            </label>
            {conditionEnabled && (
              <ConditionEditor
                value={condition}
                onChange={setCondition}
                upstreamNodes={upstreamNodes}
                readOnly={readOnly}
                emptyHint="Adicione uma regra — sem nenhuma regra, este nó sempre executa."
              />
            )}
          </div>
        )}

        {tab === "retry" && (
          <div className="grid grid-cols-2 gap-3">
            <Field>
              <Label htmlFor="node-attempts">Tentativas máximas</Label>
              <Input id="node-attempts" type="number" min={1} disabled={readOnly} value={maxAttempts} onChange={(e) => setMaxAttempts(e.target.value)} />
              <p className="text-xs text-muted-foreground">Quantas vezes tentar rodar, incluindo a 1ª tentativa.</p>
            </Field>
            <Field>
              <Label htmlFor="node-retries">Retries</Label>
              <Input id="node-retries" type="number" min={0} disabled={readOnly} value={maxRetries} onChange={(e) => setMaxRetries(e.target.value)} />
              <p className="text-xs text-muted-foreground">Novas tentativas após uma falha (0 = não tenta de novo).</p>
            </Field>
            <Field className="col-span-2">
              <Label htmlFor="node-timeout">Timeout (segundos)</Label>
              <Input id="node-timeout" type="number" min={1} placeholder="usa o timeout da automação" disabled={readOnly} value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(e.target.value)} />
              <p className="text-xs text-muted-foreground">Deixe em branco para usar o timeout padrão configurado na automação.</p>
            </Field>
            <Field className="col-span-2">
              <Label htmlFor="node-dependency-policy">Política de dependência</Label>
              <Select id="node-dependency-policy" value={dependencyPolicy} disabled={readOnly} onChange={(e) => setDependencyPolicy(e.target.value)}>
                <option value="all">Aguardar todas as entradas (all)</option>
                <option value="any">Seguir com a primeira entrada pronta (any)</option>
              </Select>
              <p className="text-xs text-muted-foreground">Só importa se este nó tiver mais de uma conexão chegando nele.</p>
            </Field>
          </div>
        )}

        {tab === "failure" && (
          <Field>
            <Label htmlFor="node-failure-policy">O que fazer quando este nó falhar</Label>
            <Select id="node-failure-policy" value={failurePolicy} disabled={readOnly} onChange={(e) => setFailurePolicy(e.target.value as FlowFailurePolicy)}>
              <option value="fail_flow">Falhar o Fluxo inteiro</option>
              <option value="continue">Continuar normalmente</option>
              <option value="skip_dependents">Pular os nós dependentes</option>
              <option value="continue_alternative_path">Seguir por caminho alternativo (aresta de falha)</option>
            </Select>
            <p className="text-xs text-muted-foreground">
              &quot;Caminho alternativo&quot; só funciona se este nó tiver uma conexão do tipo &quot;Falha&quot; saindo dele.
            </p>
          </Field>
        )}

        {node.data.issues.length > 0 && (
          <div className="flex flex-wrap gap-1.5 border-t border-border pt-3">
            {node.data.issues.map((issue, i) => (
              <Badge key={i} tone="destructive" className="text-[10px]">
                {issue.code}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </Sheet>
  );
}
