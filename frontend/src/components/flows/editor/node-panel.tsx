"use client";

import { useEffect, useState } from "react";
import { Trash2, AlertTriangle } from "lucide-react";

import { Sheet } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Label, Select } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { ConditionEditor } from "@/components/flows/editor/condition-editor";
import { MappingEditor } from "@/components/flows/editor/mapping-editor";
import { SwitchCaseEditor } from "@/components/flows/editor/switch-editor";
import { ifElseRule, switchConfigOf, type SwitchConfig } from "@/components/flows/editor/branch-logic";
import type { FlowCanvasNode } from "@/components/flows/editor/types";
import type { FlowFailurePolicy, FlowNodeType } from "@/types/flow";

/** Rótulo curto para o subtítulo do painel — mais legível que o node_type cru. */
function nodeTypeLabel(nodeType: FlowNodeType): string {
  const labels: Record<FlowNodeType, string> = {
    automation: "Automação",
    condition: "Regra de continuidade",
    join: "Join",
    if_else: "If / Else",
    switch: "Switch",
    merge: "Merge Data",
    set_variable: "Set Variable",
    map_fields: "Map Fields",
    transform_data: "Transform Data",
  };
  return labels[nodeType] ?? nodeType;
}

/** Texto de apoio da aba "Etapa" para tipos que não são automation — cada bloco aponta para
 * a aba certa em vez de repetir o mesmo texto genérico para todos. */
function stepHintFor(nodeType: FlowNodeType): string {
  switch (nodeType) {
    case "if_else":
      return "Use a aba Verdadeiro / Falso para definir a regra. As duas saídas já ficam conectadas automaticamente às arestas certas.";
    case "switch":
      return "Use a aba Casos para definir o campo testado e os valores que geram cada saída.";
    case "condition":
      return "Use a aba Quando para definir o teste que decide se este passo continua.";
    case "join":
      return "Use a aba Execução para definir se este ponto espera todas as entradas ou só a primeira.";
    case "merge":
      return "Use a aba Dados para escolher os campos combinados e a aba Execução para o critério de espera.";
    case "set_variable":
      return "Use a aba Dados para definir as variáveis desta etapa.";
    case "map_fields":
      return "Use a aba Dados para escolher e renomear os campos.";
    case "transform_data":
      return "Use a aba Dados para escolher o campo e a transformação aplicada.";
    default:
      return "Use a aba Execução para definir como este ponto espera as etapas anteriores.";
  }
}

type MappingCopy = { title: string; description: string; fieldLabel: string; allowTransform: boolean };

/** Copy da aba "Dados" por tipo de bloco — cada um usa o mesmo mecanismo (input_mapping),
 * mas com um propósito diferente, então o texto e os rótulos não podem ser genéricos. */
function mappingCopyFor(nodeType: FlowNodeType): MappingCopy {
  switch (nodeType) {
    case "set_variable":
      return { title: "Variáveis desta etapa", description: "Cada campo abaixo vira uma variável disponível para as próximas etapas.", fieldLabel: "nome da variável", allowTransform: false };
    case "map_fields":
      return { title: "Campos mapeados", description: "Selecione e renomeie campos vindos de etapas anteriores.", fieldLabel: "nome do campo de saída", allowTransform: false };
    case "transform_data":
      return { title: "Transformações", description: "Escolha o campo de origem e a transformação aplicada a cada um.", fieldLabel: "nome do campo de saída", allowTransform: true };
    case "merge":
      return { title: "Campos combinados", description: "Escolha quais campos de cada caminho paralelo entram no objeto final combinado.", fieldLabel: "campo do resultado combinado", allowTransform: false };
    case "if_else":
      return { title: "Dados para as próximas etapas", description: "Opcional — ajuste apenas se quiser renomear ou filtrar campos antes de seguir para Verdadeiro ou Falso.", fieldLabel: "campo que a próxima etapa espera", allowTransform: false };
    case "switch":
      return { title: "Dados para as próximas etapas", description: "Opcional — ajuste apenas se quiser renomear ou filtrar campos antes de seguir para o caso escolhido.", fieldLabel: "campo que a próxima etapa espera", allowTransform: false };
    default:
      return { title: "Inputs (entrada da automação)", description: "Por padrão, esta etapa recebe todos os dados de entrada do fluxo. Ajuste apenas os campos que precisarem mudar.", fieldLabel: "campo que a etapa espera", allowTransform: false };
  }
}

/** Estes tipos são passo-a-passo puro (produzem a saída só a partir de input_mapping — ver
 * _release_ready_nodes no backend); não faz sentido mostrar o segundo editor de
 * "output_mapping" para eles porque o motor não lê esse campo (mesmo comportamento que
 * condition/join já têm hoje — ver nota em node_type "automation"/"condition"/"join" abaixo). */
const SINGLE_MAPPING_NODE_TYPES = new Set<FlowNodeType>(["if_else", "switch", "merge", "set_variable", "map_fields", "transform_data"]);

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
  readOnly,
  onClose,
  onChangeAutomation,
  onSave,
  onDelete,
  onDuplicate,
}: {
  node: FlowCanvasNode | null;
  upstreamNodes: { key: string; name: string }[];
  readOnly: boolean;
  onClose: () => void;
  onChangeAutomation: () => void;
  onSave: (patch: NodeConfigPatch) => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const [tab, setTab] = useState("config");
  const [name, setName] = useState("");
  const [inputMapping, setInputMapping] = useState<Record<string, unknown>>({});
  const [outputMapping, setOutputMapping] = useState<Record<string, unknown>>({});
  const [condition, setCondition] = useState<Record<string, unknown> | null>(null);
  const [conditionEnabled, setConditionEnabled] = useState(false);
  const [maxAttempts, setMaxAttempts] = useState("1");
  const [maxRetries, setMaxRetries] = useState("0");
  const [timeoutSeconds, setTimeoutSeconds] = useState("");
  const [dependencyPolicy, setDependencyPolicy] = useState("all");
  const [failurePolicy, setFailurePolicy] = useState<FlowFailurePolicy>("fail_flow");
  const [rule, setRule] = useState<Record<string, unknown> | null>(null);
  const [switchConfig, setSwitchConfig] = useState<SwitchConfig>({ subject: null, cases: [], hasDefault: true });

  useEffect(() => {
    if (!node) return;
    const fn = node.data.flowNode;
    setTab("config");
    setName(fn.name || "");
    setInputMapping(fn.input_mapping || {});
    setOutputMapping(fn.output_mapping || {});
    setConditionEnabled(fn.node_type === "condition" || Boolean(fn.condition));
    setCondition(fn.condition ?? null);
    setRule(ifElseRule(fn));
    setSwitchConfig(switchConfigOf(fn));
    setMaxAttempts(String((fn.retry_policy as Record<string, unknown> | undefined)?.max_attempts ?? 1));
    setMaxRetries(String((fn.retry_policy as Record<string, unknown> | undefined)?.max_retries ?? 0));
    setTimeoutSeconds(String((fn.timeout_policy as Record<string, unknown> | undefined)?.execution_timeout_seconds ?? ""));
    setDependencyPolicy(String((fn.execution_policy as Record<string, unknown> | undefined)?.dependency_policy ?? "all"));
    setFailurePolicy(fn.failure_policy);
  }, [node]);

  if (!node) return null;
  const fn = node.data.flowNode;
  const isIfElse = fn.node_type === "if_else";
  const isSwitch = fn.node_type === "switch";

  function save() {
    onSave({
      name,
      input_mapping: inputMapping,
      output_mapping: outputMapping,
      // If/Else e Switch nunca usam node.condition — a ramificação real mora nas arestas
      // que saem de cada handle (ver branch-logic.ts). Deixar isso null evita que o próprio
      // nó fique "skipped" e quebre as saídas (ver nota em use_cases.ValidateFlowVersion).
      condition: isIfElse || isSwitch ? null : conditionEnabled ? condition : null,
      retry_policy: { max_attempts: Number(maxAttempts) || 1, max_retries: Number(maxRetries) || 0 },
      timeout_policy: timeoutSeconds ? { execution_timeout_seconds: Number(timeoutSeconds) } : {},
      failure_policy: failurePolicy,
      execution_policy: { dependency_policy: dependencyPolicy },
      configuration: isIfElse ? { ...fn.configuration, rule } : isSwitch ? { ...fn.configuration, switch: switchConfig } : fn.configuration,
    });
  }

  const nodeIssues = node.data.issues;
  const mappingCopy = mappingCopyFor(fn.node_type);
  const showOutputMapping = !SINGLE_MAPPING_NODE_TYPES.has(fn.node_type);
  const branchTabLabel = isIfElse ? "Verdadeiro / Falso" : isSwitch ? "Casos" : "Quando";

  return (
    <Sheet
      open={Boolean(node)}
      onClose={onClose}
      title={fn.name || fn.key}
      description={`${nodeTypeLabel(fn.node_type)} · ${fn.key}`}
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
            <Button onClick={save}>Salvar nó</Button>
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
            { value: "config", label: "Etapa" },
            { value: "mappings", label: "Dados" },
            { value: "condition", label: branchTabLabel },
            { value: "behavior", label: "Execução" },
          ]}
        />

        {tab === "config" && (
          <div className="space-y-4">
            <Field>
              <Label htmlFor="node-name">Nome</Label>
              <Input id="node-name" placeholder="Dê um nome que explique esta etapa" value={name} disabled={readOnly} onChange={(e) => setName(e.target.value)} />
            </Field>

            {fn.node_type === "automation" && (
              <div className="rounded-lg border border-border bg-muted/20 p-4">
                <p className="text-xs font-medium text-muted-foreground">Automação desta etapa</p>
                <p className="mt-1 text-sm font-semibold">{node.data.automationName ?? "Nenhuma automação vinculada"}</p>
                {!readOnly && (
                  <Button size="sm" variant="outline" className="mt-3" onClick={onChangeAutomation}>
                    Trocar automação
                  </Button>
                )}
              </div>
            )}

            {fn.node_type !== "automation" && (
              <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground">{stepHintFor(fn.node_type)}</div>
            )}
          </div>
        )}

        {tab === "mappings" && (
          <div className="space-y-6">
            <MappingEditor
              title={mappingCopy.title}
              description={mappingCopy.description}
              fieldLabel={mappingCopy.fieldLabel}
              allowTransform={mappingCopy.allowTransform}
              mapping={inputMapping}
              upstreamNodes={upstreamNodes}
              onChange={setInputMapping}
              readOnly={readOnly}
            />
            {/* output_mapping não é lido pelo motor para estes tipos (nem para automation, hoje —
                ver SINGLE_MAPPING_NODE_TYPES acima); evitamos mostrar um segundo editor que não
                teria efeito nenhum na execução real do Flow. */}
            {showOutputMapping && (
              <div className="border-t border-border pt-4">
                <MappingEditor
                  title="Dados disponibilizados para as próximas etapas"
                  description="Opcional. Use somente quando quiser renomear ou selecionar parte do resultado desta etapa."
                  mapping={outputMapping}
                  upstreamNodes={upstreamNodes}
                  onChange={setOutputMapping}
                  readOnly={readOnly}
                />
              </div>
            )}
          </div>
        )}

        {tab === "condition" && (
          <div className="space-y-3">
            {isIfElse ? (
              <>
                <p className="text-sm text-muted-foreground">
                  Defina a regra que decide entre as duas saídas. Verdadeiro e Falso já ficam conectados automaticamente às arestas certas — não é preciso configurar as conexões manualmente.
                </p>
                <ConditionEditor
                  value={rule}
                  onChange={setRule}
                  upstreamNodes={upstreamNodes}
                  readOnly={readOnly}
                  emptyHint="Sem regra definida: a saída Verdadeiro sempre segue."
                />
              </>
            ) : isSwitch ? (
              <>
                <p className="text-sm text-muted-foreground">Defina o campo testado e os valores que geram cada saída. Cada caso e a saída Padrão já ficam conectados automaticamente às arestas certas.</p>
                <SwitchCaseEditor value={switchConfig} onChange={setSwitchConfig} upstreamNodes={upstreamNodes} readOnly={readOnly} />
              </>
            ) : fn.node_type === "condition" ? (
              <>
                <p className="text-sm text-muted-foreground">Defina o que precisa acontecer para este bloco liberar o próximo caminho.</p>
                <ConditionEditor
                  value={condition}
                  onChange={setCondition}
                  upstreamNodes={upstreamNodes}
                  readOnly={readOnly}
                  emptyHint="Escolha uma regra para este bloco de condição."
                />
              </>
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={conditionEnabled} disabled={readOnly} onChange={(e) => setConditionEnabled(e.target.checked)} />
                  Executar esta etapa somente quando a condição for atendida
                </label>
                {conditionEnabled && (
                  <ConditionEditor
                    value={condition}
                    onChange={setCondition}
                    upstreamNodes={upstreamNodes}
                    readOnly={readOnly}
                    emptyHint="Adicione uma regra para controlar quando esta etapa roda."
                  />
                )}
              </>
            )}
          </div>
        )}

        {tab === "behavior" && (
          <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3">
            <Field>
              <Label htmlFor="node-attempts">Tentativas</Label>
              <Input id="node-attempts" type="number" min={1} disabled={readOnly} value={maxAttempts} onChange={(e) => setMaxAttempts(e.target.value)} />
              <p className="text-xs text-muted-foreground">Use 1 para executar uma única vez.</p>
            </Field>
            <Field>
              <Label htmlFor="node-retries">Tentar novamente após falha</Label>
              <Input id="node-retries" type="number" min={0} disabled={readOnly} value={maxRetries} onChange={(e) => setMaxRetries(e.target.value)} />
              <p className="text-xs text-muted-foreground">Use 0 para não tentar novamente.</p>
            </Field>
            <Field className="col-span-2">
              <Label htmlFor="node-timeout">Timeout (segundos)</Label>
              <Input id="node-timeout" type="number" min={1} placeholder="usa o timeout da automação" disabled={readOnly} value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(e.target.value)} />
              <p className="text-xs text-muted-foreground">Deixe em branco para usar o timeout padrão configurado na automação.</p>
            </Field>
            <Field className="col-span-2">
              <Label htmlFor="node-dependency-policy">Quando esta etapa pode começar</Label>
              <Select id="node-dependency-policy" value={dependencyPolicy} disabled={readOnly} onChange={(e) => setDependencyPolicy(e.target.value)}>
                <option value="all">Aguardar todas as entradas (all)</option>
                <option value="any">Seguir com a primeira entrada pronta (any)</option>
              </Select>
              <p className="text-xs text-muted-foreground">Só importa quando houver mais de uma conexão chegando nesta etapa.</p>
            </Field>
          </div>
          <div className="border-t border-border pt-5">
            <Field>
              <Label htmlFor="node-failure-policy">Quando esta etapa falhar</Label>
              <Select id="node-failure-policy" value={failurePolicy} disabled={readOnly} onChange={(e) => setFailurePolicy(e.target.value as FlowFailurePolicy)}>
                <option value="fail_flow">Parar todo o fluxo</option>
                <option value="continue">Continuar as outras etapas</option>
                <option value="skip_dependents">Pular as etapas que dependem dela</option>
                <option value="continue_alternative_path">Seguir por uma conexão de falha</option>
              </Select>
              <p className="text-xs text-muted-foreground">Escolha como o processo deve reagir. O caminho de falha precisa estar conectado no diagrama.</p>
            </Field>
          </div>
          </div>
        )}

        {node.data.issues.length > 0 && (
          <div className="flex flex-wrap gap-1.5 border-t border-border pt-3">
            {node.data.issues.map((issue, i) => (
              <Badge key={i} tone="destructive" className="text-xs">
                {issue.code}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </Sheet>
  );
}
