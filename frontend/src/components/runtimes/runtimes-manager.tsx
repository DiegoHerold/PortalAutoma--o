"use client";

import { useMemo, useRef, useState, type ReactNode } from "react";
import { Archive, Ban, Boxes, Plus, Rocket, Search, Server, ShieldAlert } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { RuntimeVersionStatusBadge } from "@/components/ui/status-badge";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import {
  blockRuntimeVersion,
  createRuntime,
  createRuntimeVersion,
  deprecateRuntimeVersion,
  publishRuntimeVersion,
} from "@/lib/catalog-api";
import { isSemverBelow, normalizeCatalogKey } from "@/lib/catalog-utils";
import { createIdempotencyKey } from "@/lib/idempotency";
import { formatDateTime } from "@/lib/utils";
import type { Agent } from "@/types/agent";
import type { RuntimeResponse, RuntimeVersionResponse } from "@/types/catalog";

const VERSION_ACTIONS = {
  canPublish: (status: string) => !["published", "deprecated", "blocked"].includes(status),
  canDeprecate: (status: string) => status === "published",
  canBlock: (status: string) => status !== "blocked",
};

export function RuntimesManager() {
  const { token } = useAuth();
  const { toast } = useToast();
  const runtimes = useApi<RuntimeResponse[]>("/runtimes");
  const agents = useApi<Agent[]>("/agents");
  const [query, setQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busyVersionId, setBusyVersionId] = useState<string | null>(null);

  const selected = (runtimes.data ?? []).find((runtime) => runtime.id === selectedId) ?? null;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (runtimes.data ?? []).filter((runtime) => {
      if (!q) return true;
      return runtime.name.toLowerCase().includes(q) || runtime.key.toLowerCase().includes(q);
    });
  }, [query, runtimes.data]);

  async function refetchRuntime() {
    await runtimes.refetch();
  }

  async function runVersionAction(
    version: RuntimeVersionResponse,
    action: "publish" | "deprecate" | "block",
    fn: (token: string) => Promise<RuntimeVersionResponse>,
  ) {
    if (!token) return;
    if (action === "publish" && !window.confirm(`Publicar Runtime ${version.version}?`)) return;
    if (action === "deprecate" && !window.confirm(`Depreciar Runtime ${version.version}? Novos usos devem preferir outra versao.`)) return;
    setBusyVersionId(version.id);
    try {
      await fn(token);
      toast({ title: "Versao de runtime atualizada", kind: "success" });
      await refetchRuntime();
    } catch (err) {
      toast({ title: "Falha na acao", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusyVersionId(null);
    }
  }

  async function handleBlock(version: RuntimeVersionResponse) {
    if (!token) return;
    if (!window.confirm(`Bloquear Runtime ${version.version}? Esta acao impede novos usos conforme as regras do backend.`)) return;
    const reason = window.prompt("Motivo do bloqueio (opcional):") ?? "";
    await runVersionAction(version, "block", (t) => blockRuntimeVersion(t, version.id, { reason: reason || null }));
  }

  if (runtimes.error) return <ErrorState message={runtimes.error} onRetry={runtimes.refetch} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar por nome ou chave..." value={query} onChange={(event) => setQuery(event.target.value)} />
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" /> Novo runtime
        </Button>
      </div>

      {runtimes.loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-44 rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Boxes}
          title="Nenhum runtime"
          description={query ? "Nenhum resultado para a busca atual." : "Crie o primeiro runtime para publicar versoes compativeis com Agents."}
          action={
            !query ? (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" /> Novo runtime
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((runtime) => (
            <RuntimeCard key={runtime.id} runtime={runtime} onOpen={() => setSelectedId(runtime.id)} />
          ))}
        </div>
      )}

      <RuntimeCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={async (runtime) => {
          setCreateOpen(false);
          setSelectedId(runtime.id);
          await refetchRuntime();
        }}
      />

      <Sheet
        open={Boolean(selected)}
        onClose={() => setSelectedId(null)}
        title={selected?.name}
        description={selected ? `${selected.key} - ${selected.id}` : undefined}
        widthClassName="w-full sm:max-w-4xl"
        footer={
          selected ? (
            <Button onClick={() => setVersionOpen(true)}>
              <Plus className="h-4 w-4" /> Nova versao
            </Button>
          ) : undefined
        }
      >
        {selected && (
          <RuntimeDetails
            runtime={selected}
            agents={agents.data ?? []}
            agentsLoading={agents.loading}
            busyVersionId={busyVersionId}
            onPublish={(version) => runVersionAction(version, "publish", (t) => publishRuntimeVersion(t, version.id))}
            onDeprecate={(version) => runVersionAction(version, "deprecate", (t) => deprecateRuntimeVersion(t, version.id))}
            onBlock={handleBlock}
          />
        )}
      </Sheet>

      {selected && (
        <RuntimeVersionCreateModal
          runtime={selected}
          open={versionOpen}
          onClose={() => setVersionOpen(false)}
          onCreated={async () => {
            setVersionOpen(false);
            await refetchRuntime();
          }}
        />
      )}
    </div>
  );
}

function RuntimeCard({ runtime, onOpen }: { runtime: RuntimeResponse; onOpen: () => void }) {
  const versions = runtime.versions ?? [];
  const published = versions.find((version) => version.status === "published");
  return (
    <button
      type="button"
      onClick={onOpen}
      className="h-full rounded-lg border border-border bg-card p-5 text-left shadow-sm transition-colors hover:border-primary/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-display text-base font-semibold">{runtime.name}</h2>
          <p className="tabular mt-1 truncate text-xs text-muted-foreground">{runtime.key}</p>
        </div>
        <Badge tone={runtime.status === "active" ? "success" : "neutral"}>{runtime.status}</Badge>
      </div>
      {runtime.description && <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{runtime.description}</p>}
      <div className="mt-4 grid gap-2 text-xs text-muted-foreground">
        <span>{versions.length} versao(oes)</span>
        <span className="tabular">{published ? `Publicada: ${published.version}` : "Sem versao publicada"}</span>
      </div>
    </button>
  );
}

function RuntimeDetails({
  runtime,
  agents,
  agentsLoading,
  busyVersionId,
  onPublish,
  onDeprecate,
  onBlock,
}: {
  runtime: RuntimeResponse;
  agents: Agent[];
  agentsLoading: boolean;
  busyVersionId: string | null;
  onPublish: (version: RuntimeVersionResponse) => void;
  onDeprecate: (version: RuntimeVersionResponse) => void;
  onBlock: (version: RuntimeVersionResponse) => void;
}) {
  const [tab, setTab] = useState("overview");
  const versions = runtime.versions ?? [];
  return (
    <div className="space-y-5">
      <Tabs
        value={tab}
        onValueChange={setTab}
        items={[
          { value: "overview", label: "Resumo" },
          { value: "versions", label: "Versoes", count: versions.length },
          { value: "compatibility", label: "Agents" },
        ]}
      />

      {tab === "overview" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Meta label="Chave" value={runtime.key} />
          <Meta label="Runtime ID" value={<span className="tabular text-xs">{runtime.id}</span>} />
          <Meta label="Status" value={runtime.status} />
          <Meta label="Criado em" value={formatDateTime(runtime.created_at)} />
          <Meta label="Atualizado em" value={formatDateTime(runtime.updated_at)} />
          <Meta label="Versoes" value={versions.length} />
          {runtime.description && <div className="sm:col-span-2"><Meta label="Descricao" value={runtime.description} /></div>}
        </div>
      )}

      {tab === "versions" && (
        versions.length === 0 ? (
          <EmptyState icon={Boxes} title="Sem versoes" description="Crie uma RuntimeVersion para definir plataforma, entrypoints e modos suportados." />
        ) : (
          <div className="space-y-3">
            {versions.map((version) => (
              <RuntimeVersionItem
                key={version.id}
                version={version}
                busy={busyVersionId === version.id}
                onPublish={() => onPublish(version)}
                onDeprecate={() => onDeprecate(version)}
                onBlock={() => onBlock(version)}
              />
            ))}
          </div>
        )
      )}

      {tab === "compatibility" && (
        <RuntimeAgentCompatibility versions={versions} agents={agents} loading={agentsLoading} />
      )}
    </div>
  );
}

function RuntimeVersionItem({
  version,
  busy,
  onPublish,
  onDeprecate,
  onBlock,
}: {
  version: RuntimeVersionResponse;
  busy: boolean;
  onPublish: () => void;
  onDeprecate: () => void;
  onBlock: () => void;
}) {
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="tabular font-medium">v{version.version}</span>
            <RuntimeVersionStatusBadge status={version.status} />
            <Badge tone="outline">{version.operating_system}</Badge>
            <Badge tone="outline">{version.architecture}</Badge>
          </div>
          <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
            <span>Agent minimo: {version.minimum_agent_version ?? "-"}</span>
            <span>Criada: {formatDateTime(version.created_at)}</span>
            <span>Entrypoints: {version.supported_entrypoints.join(", ") || "-"}</span>
            <span>Modos: {version.supported_execution_modes.join(", ") || "-"}</span>
          </div>
          {Object.keys(version.metadata || {}).length > 0 && (
            <pre className="mt-3 max-h-32 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(version.metadata, null, 2)}</pre>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {VERSION_ACTIONS.canPublish(version.status) && (
            <Button size="sm" disabled={busy} onClick={onPublish}>
              <Rocket className="h-3.5 w-3.5" /> Publicar
            </Button>
          )}
          {VERSION_ACTIONS.canDeprecate(version.status) && (
            <Button size="sm" variant="outline" disabled={busy} onClick={onDeprecate}>
              <Archive className="h-3.5 w-3.5" /> Depreciar
            </Button>
          )}
          {VERSION_ACTIONS.canBlock(version.status) && (
            <Button size="sm" variant="destructive" disabled={busy} onClick={onBlock}>
              <Ban className="h-3.5 w-3.5" /> Bloquear
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function RuntimeAgentCompatibility({
  versions,
  agents,
  loading,
}: {
  versions: RuntimeVersionResponse[];
  agents: Agent[];
  loading: boolean;
}) {
  if (loading) return <Skeleton className="h-28 rounded-lg" />;
  const versionsWithMinimum = versions.filter((version) => version.minimum_agent_version);
  if (versionsWithMinimum.length === 0) {
    return <EmptyState icon={Server} title="Sem requisito minimo" description="Nenhuma versao deste runtime exige minimum_agent_version." />;
  }
  return (
    <div className="space-y-3">
      {versionsWithMinimum.map((version) => {
        const older = agents.filter((agent) => isSemverBelow(agent.current_version, version.minimum_agent_version));
        return (
          <div key={version.id} className="rounded-lg border border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium">Runtime {version.version}</p>
                <p className="text-sm text-muted-foreground">Exige Agent {version.minimum_agent_version} ou superior.</p>
              </div>
              <Badge tone={older.length > 0 ? "warning" : "success"}>{older.length} Agent(s) abaixo</Badge>
            </div>
            {older.length > 0 && (
              <div className="mt-3 flex items-start gap-2 rounded-md bg-warning/10 p-3 text-sm text-warning">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  {older.length} Agent(s) registrados possuem versao anterior. Este aviso e informativo; o backend continua decidindo admissao e execucao.
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function RuntimeCreateModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (runtime: RuntimeResponse) => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const idempotencyKey = useRef(createIdempotencyKey("runtime:create"));

  async function submit() {
    if (!token || !key.trim() || !name.trim()) return;
    setSubmitting(true);
    try {
      const runtime = await createRuntime(token, { key: normalizeCatalogKey(key), name: name.trim(), description: description.trim() || null }, idempotencyKey.current);
      toast({ title: "Runtime criado", kind: "success" });
      idempotencyKey.current = createIdempotencyKey("runtime:create");
      setKey("");
      setName("");
      setDescription("");
      onCreated(runtime);
    } catch (err) {
      toast({ title: "Falha ao criar runtime", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo runtime"
      description="Cadastre a identidade logica do runtime antes de adicionar versoes."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={submit} disabled={submitting || !key.trim() || !name.trim()}>Criar runtime</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field>
          <Label htmlFor="runtime-key">Chave</Label>
          <Input id="runtime-key" value={key} onChange={(event) => setKey(normalizeCatalogKey(event.target.value))} placeholder="python-desktop" />
        </Field>
        <Field>
          <Label htmlFor="runtime-name">Nome</Label>
          <Input id="runtime-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Python Desktop" />
        </Field>
        <Field>
          <Label htmlFor="runtime-description">Descricao</Label>
          <Textarea id="runtime-description" value={description} onChange={(event) => setDescription(event.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function RuntimeVersionCreateModal({
  runtime,
  open,
  onClose,
  onCreated,
}: {
  runtime: RuntimeResponse;
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [version, setVersion] = useState("");
  const [operatingSystem, setOperatingSystem] = useState("windows");
  const [architecture, setArchitecture] = useState("x64");
  const [minimumAgentVersion, setMinimumAgentVersion] = useState("");
  const [entrypoints, setEntrypoints] = useState(["python-function"]);
  const [executionModes, setExecutionModes] = useState(["interactive", "background"]);
  const [entryDraft, setEntryDraft] = useState("");
  const [modeDraft, setModeDraft] = useState("");
  const [metadataRows, setMetadataRows] = useState<Array<{ key: string; value: string }>>([]);
  const [advancedMetadata, setAdvancedMetadata] = useState(false);
  const [metadataJson, setMetadataJson] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const idempotencyKey = useRef(createIdempotencyKey("runtime-version:create"));

  function metadata(): Record<string, unknown> | null {
    if (advancedMetadata) {
      try {
        const parsed = JSON.parse(metadataJson) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          setError("Metadata JSON deve ser um objeto.");
          return null;
        }
        return parsed as Record<string, unknown>;
      } catch {
        setError("Metadata JSON invalido.");
        return null;
      }
    }
    return Object.fromEntries(metadataRows.filter((row) => row.key.trim()).map((row) => [row.key.trim(), row.value]));
  }

  async function submit() {
    if (!token || !version.trim()) return;
    const parsedMetadata = metadata();
    if (!parsedMetadata) return;
    setError(null);
    setSubmitting(true);
    try {
      await createRuntimeVersion(
        token,
        runtime.id,
        {
          version: version.trim(),
          operating_system: operatingSystem || "windows",
          architecture: architecture || "x64",
          minimum_agent_version: minimumAgentVersion.trim() || null,
          supported_entrypoints: entrypoints,
          supported_execution_modes: executionModes,
          metadata: parsedMetadata,
        },
        idempotencyKey.current,
      );
      toast({ title: "Versao de runtime criada", kind: "success" });
      idempotencyKey.current = createIdempotencyKey("runtime-version:create");
      setVersion("");
      onCreated();
    } catch (err) {
      toast({ title: "Falha ao criar versao", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Nova versao de ${runtime.name}`}
      description="Defina plataforma, entrypoints, modos e metadata da RuntimeVersion."
      className="max-w-2xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={submit} disabled={submitting || !version.trim() || entrypoints.length === 0 || executionModes.length === 0}>Criar versao</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field>
            <Label htmlFor="runtime-version">Versao</Label>
            <Input id="runtime-version" className="tabular" value={version} onChange={(event) => setVersion(event.target.value)} placeholder="1.0.0" />
          </Field>
          <Field>
            <Label htmlFor="runtime-os">Sistema</Label>
            <Input id="runtime-os" value={operatingSystem} onChange={(event) => setOperatingSystem(event.target.value)} />
          </Field>
          <Field>
            <Label htmlFor="runtime-arch">Arquitetura</Label>
            <Input id="runtime-arch" value={architecture} onChange={(event) => setArchitecture(event.target.value)} />
          </Field>
        </div>
        <Field>
          <Label htmlFor="runtime-min-agent">Agent minimo</Label>
          <Input id="runtime-min-agent" className="tabular" value={minimumAgentVersion} onChange={(event) => setMinimumAgentVersion(event.target.value)} placeholder="1.4.0" />
        </Field>
        <EditableList
          label="Entrypoints"
          value={entryDraft}
          values={entrypoints}
          onValueChange={setEntryDraft}
          onAdd={() => addListValue(entryDraft, entrypoints, setEntrypoints, setEntryDraft)}
          onRemove={(item) => setEntrypoints((prev) => prev.filter((value) => value !== item))}
          placeholder="python-module"
        />
        <EditableList
          label="Modos de execucao"
          value={modeDraft}
          values={executionModes}
          onValueChange={setModeDraft}
          onAdd={() => addListValue(modeDraft, executionModes, setExecutionModes, setModeDraft)}
          onRemove={(item) => setExecutionModes((prev) => prev.filter((value) => value !== item))}
          placeholder="background"
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={advancedMetadata} onChange={(event) => setAdvancedMetadata(event.target.checked)} />
          Editar metadata como JSON
        </label>
        {advancedMetadata ? (
          <Field>
            <Label htmlFor="runtime-metadata-json">Metadata JSON</Label>
            <Textarea id="runtime-metadata-json" className="min-h-[140px] font-mono text-xs" value={metadataJson} onChange={(event) => setMetadataJson(event.target.value)} />
          </Field>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>Metadata</Label>
              <Button size="sm" variant="outline" onClick={() => setMetadataRows((prev) => [...prev, { key: "", value: "" }])}>
                <Plus className="h-3.5 w-3.5" /> Campo
              </Button>
            </div>
            {metadataRows.length === 0 ? (
              <p className="text-xs text-muted-foreground">Nenhum metadado adicional.</p>
            ) : (
              metadataRows.map((row, index) => (
                <div key={index} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                  <Input value={row.key} onChange={(event) => updateMetadataRow(index, "key", event.target.value, setMetadataRows)} placeholder="chave" />
                  <Input value={row.value} onChange={(event) => updateMetadataRow(index, "value", event.target.value, setMetadataRows)} placeholder="valor" />
                  <Button size="sm" variant="ghost" onClick={() => setMetadataRows((prev) => prev.filter((_, itemIndex) => itemIndex !== index))}>Remover</Button>
                </div>
              ))
            )}
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </Modal>
  );
}

function EditableList({
  label,
  values,
  value,
  placeholder,
  onValueChange,
  onAdd,
  onRemove,
}: {
  label: string;
  values: string[];
  value: string;
  placeholder: string;
  onValueChange: (value: string) => void;
  onAdd: () => void;
  onRemove: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex gap-2">
        <Input value={value} onChange={(event) => onValueChange(event.target.value)} placeholder={placeholder} />
        <Button variant="outline" onClick={onAdd}>Adicionar</Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {values.map((item) => (
          <Badge key={item} tone="outline" className="gap-2">
            {item}
            <button type="button" onClick={() => onRemove(item)} className="text-muted-foreground hover:text-foreground">
              x
            </button>
          </Badge>
        ))}
      </div>
    </div>
  );
}

function addListValue(
  draft: string,
  values: string[],
  setValues: (updater: (previous: string[]) => string[]) => void,
  setDraft: (value: string) => void,
) {
  const value = draft.trim();
  if (!value || values.includes(value)) return;
  setValues((previous) => [...previous, value]);
  setDraft("");
}

function updateMetadataRow(
  index: number,
  key: "key" | "value",
  value: string,
  setRows: (updater: (previous: Array<{ key: string; value: string }>) => Array<{ key: string; value: string }>) => void,
) {
  setRows((previous) => previous.map((row, itemIndex) => (itemIndex === index ? { ...row, [key]: value } : row)));
}

function Meta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
