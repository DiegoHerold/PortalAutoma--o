"use client";

import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { Archive, Ban, FileArchive, Package, Plus, Rocket, ShieldCheck, Upload } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { AutomationVersionStatusBadge } from "@/components/ui/status-badge";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import {
  abortPackageUpload,
  blockAutomationVersion,
  completePackageUpload,
  createAutomationVersion,
  deprecateAutomationVersion,
  initiatePackageUpload,
  publishAutomationVersion,
  putPackageFile,
  validateAutomationVersion,
  type UploadProgress,
} from "@/lib/catalog-api";
import { defaultAutomationManifest, formatBytes, normalizeValidationErrors, sha256File } from "@/lib/catalog-utils";
import { createIdempotencyKey } from "@/lib/idempotency";
import { formatDateTime } from "@/lib/utils";
import type { Automation } from "@/types/automation";
import type { AutomationVersionResponse, PackageResponse, PackageUploadResponse } from "@/types/catalog";

const AUTOMATION_VERSION_ACTIONS = {
  canUpload: (status: string) => !["published", "deprecated", "blocked"].includes(status),
  canValidate: (status: string) => !["published", "deprecated", "blocked"].includes(status),
  canPublish: (status: string) => !["published", "deprecated", "blocked"].includes(status),
  canDeprecate: (status: string) => status === "published",
  canBlock: (status: string) => status !== "blocked",
};

export function AutomationVersionsPanel({ automation }: { automation: Automation }) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [pollWhileValidating, setPollWhileValidating] = useState(false);
  const versions = useApi<AutomationVersionResponse[]>(`/automations/${automation.id}/versions`, {
    pollMs: pollWhileValidating ? 3000 : undefined,
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [uploadTarget, setUploadTarget] = useState<AutomationVersionResponse | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busyVersionId, setBusyVersionId] = useState<number | null>(null);

  useEffect(() => {
    if (!versions.data) return;
    if (!versions.data.some((version) => version.status === "validating")) setPollWhileValidating(false);
  }, [versions.data]);

  const selected = (versions.data ?? []).find((version) => version.id === selectedId) ?? null;

  async function refetch() {
    await versions.refetch();
  }

  async function runAction(
    version: AutomationVersionResponse,
    successTitle: string,
    fn: (token: string) => Promise<AutomationVersionResponse>,
  ) {
    if (!token) return;
    setBusyVersionId(version.id);
    try {
      const updated = await fn(token);
      toast({ title: successTitle, kind: "success" });
      versions.mutate((previous) => (previous ?? []).map((item) => (item.id === updated.id ? updated : item)));
      await refetch();
    } catch (err) {
      toast({ title: "Falha na acao", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusyVersionId(null);
    }
  }

  async function handleValidate(version: AutomationVersionResponse) {
    if (!window.confirm(`Validar v${version.version}?`)) return;
    setPollWhileValidating(true);
    await runAction(version, "Validacao solicitada", (t) => validateAutomationVersion(t, version.id));
  }

  async function handlePublish(version: AutomationVersionResponse) {
    if (!version.package_id) {
      toast({ title: "Pacote ausente", description: "Envie e conclua um pacote antes de publicar.", kind: "warning" });
      return;
    }
    const validationText = version.validation_errors?.length ? `${version.validation_errors.length} erro(s) conhecidos` : "sem erros conhecidos";
    if (!window.confirm(`Publicar v${version.version}? Ultima validacao: ${validationText}. A versao ficara disponivel para Flows.`)) return;
    await runAction(version, "Versao publicada", (t) => publishAutomationVersion(t, version.id));
  }

  async function handleDeprecate(version: AutomationVersionResponse) {
    if (!window.confirm("Depreciar esta versao? Ela deixa de ser recomendada para novos usos, mas nao e necessariamente bloqueada.")) return;
    await runAction(version, "Versao depreciada", (t) => deprecateAutomationVersion(t, version.id));
  }

  async function handleBlock(version: AutomationVersionResponse) {
    if (!window.confirm("Bloquear esta versao? O impacto final segue as regras do backend.")) return;
    const reason = window.prompt("Motivo do bloqueio (opcional):") ?? "";
    await runAction(version, "Versao bloqueada", (t) => blockAutomationVersion(t, version.id, { reason: reason || null }));
  }

  return (
    <>
      <SectionCard
        title="Versoes"
        description="Manifesto, pacote, validacao e publicacao de AutomationVersion"
        bodyClassName="p-0"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> Nova versao
          </Button>
        }
      >
        {versions.loading ? (
          <div className="p-5">
            <Skeleton className="h-24 rounded-lg" />
          </div>
        ) : (versions.data ?? []).length === 0 ? (
          <div className="p-5">
            <EmptyState icon={Package} title="Sem versoes" description="Crie uma versao com manifesto YAML e depois envie um pacote ZIP." />
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {versions.data!.map((version) => (
              <li key={version.id} className="px-5 py-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <button type="button" className="min-w-0 text-left" onClick={() => setSelectedId(version.id)}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="tabular text-sm font-medium">v{version.version}</span>
                      <AutomationVersionStatusBadge status={version.status} />
                      <Badge tone="outline">{version.runtime_id}{version.runtime_version ? `@${version.runtime_version}` : ""}</Badge>
                    </div>
                    <p className="tabular mt-1 truncate text-xs text-muted-foreground">
                      {version.package_id ? `Pacote ${version.package_id}` : "Sem pacote"} - {formatBytes(version.artifact_size)} - {version.artifact_sha256.slice(0, 12) || "sha pendente"}
                    </p>
                  </button>
                  <VersionActions
                    version={version}
                    busy={busyVersionId === version.id}
                    onUpload={() => setUploadTarget(version)}
                    onValidate={() => handleValidate(version)}
                    onPublish={() => handlePublish(version)}
                    onDeprecate={() => handleDeprecate(version)}
                    onBlock={() => handleBlock(version)}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <AutomationVersionCreateModal
        automation={automation}
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={async (version) => {
          setCreateOpen(false);
          setSelectedId(version.id);
          await refetch();
        }}
      />

      {uploadTarget && (
        <AutomationPackageUploadModal
          version={uploadTarget}
          open={Boolean(uploadTarget)}
          onClose={() => setUploadTarget(null)}
          onCompleted={async () => {
            setUploadTarget(null);
            await refetch();
          }}
        />
      )}

      <Sheet
        open={Boolean(selected)}
        onClose={() => setSelectedId(null)}
        title={selected ? `AutomationVersion v${selected.version}` : undefined}
        description={selected ? `#${selected.id} - ${selected.status}` : undefined}
        widthClassName="w-full sm:max-w-4xl"
      >
        {selected && <AutomationVersionDetails version={selected} />}
      </Sheet>
    </>
  );
}

function VersionActions({
  version,
  busy,
  onUpload,
  onValidate,
  onPublish,
  onDeprecate,
  onBlock,
}: {
  version: AutomationVersionResponse;
  busy: boolean;
  onUpload: () => void;
  onValidate: () => void;
  onPublish: () => void;
  onDeprecate: () => void;
  onBlock: () => void;
}) {
  return (
    <div className="flex shrink-0 flex-wrap gap-2">
      {AUTOMATION_VERSION_ACTIONS.canUpload(version.status) && (
        <Button size="sm" variant="outline" disabled={busy} onClick={onUpload}>
          <Upload className="h-3.5 w-3.5" /> Pacote
        </Button>
      )}
      {AUTOMATION_VERSION_ACTIONS.canValidate(version.status) && (
        <Button size="sm" variant="outline" disabled={busy} onClick={onValidate}>
          <ShieldCheck className="h-3.5 w-3.5" /> Validar
        </Button>
      )}
      {AUTOMATION_VERSION_ACTIONS.canPublish(version.status) && (
        <Button size="sm" disabled={busy || !version.package_id} onClick={onPublish}>
          <Rocket className="h-3.5 w-3.5" /> Publicar
        </Button>
      )}
      {AUTOMATION_VERSION_ACTIONS.canDeprecate(version.status) && (
        <Button size="sm" variant="outline" disabled={busy} onClick={onDeprecate}>
          <Archive className="h-3.5 w-3.5" /> Depreciar
        </Button>
      )}
      {AUTOMATION_VERSION_ACTIONS.canBlock(version.status) && (
        <Button size="sm" variant="destructive" disabled={busy} onClick={onBlock}>
          <Ban className="h-3.5 w-3.5" /> Bloquear
        </Button>
      )}
    </div>
  );
}

function AutomationVersionCreateModal({
  automation,
  open,
  onClose,
  onCreated,
}: {
  automation: Automation;
  open: boolean;
  onClose: () => void;
  onCreated: (version: AutomationVersionResponse) => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const automationKey = automation.key ?? automation.slug;
  const [rawManifest, setRawManifest] = useState(defaultAutomationManifest(automationKey));
  const [releaseNotes, setReleaseNotes] = useState("");
  const [sourceRepository, setSourceRepository] = useState("");
  const [sourceBranch, setSourceBranch] = useState("");
  const [sourceTag, setSourceTag] = useState("");
  const [sourceCommitSha, setSourceCommitSha] = useState("");
  const [buildId, setBuildId] = useState("");
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const idempotencyKey = useRef(createIdempotencyKey("automation-version:create"));

  async function submit() {
    if (!token) return;
    const trimmed = rawManifest.trim();
    if (!trimmed) {
      setManifestError("Informe o manifesto YAML.");
      return;
    }
    if (!trimmed.includes("schema_version") || !trimmed.includes("runtime:") || !trimmed.includes("entrypoint:")) {
      setManifestError("O manifesto deve conter schema_version, runtime e entrypoint.");
      return;
    }
    setManifestError(null);
    setSubmitting(true);
    try {
      const version = await createAutomationVersion(
        token,
        automation.id,
        {
          raw_manifest: trimmed,
          release_notes: releaseNotes.trim() || null,
          source_repository: sourceRepository.trim() || null,
          source_branch: sourceBranch.trim() || null,
          source_tag: sourceTag.trim() || null,
          source_commit_sha: sourceCommitSha.trim() || null,
          build_id: buildId.trim() || null,
        },
        idempotencyKey.current,
      );
      toast({ title: "Versao criada", kind: "success" });
      idempotencyKey.current = createIdempotencyKey("automation-version:create");
      onCreated(version);
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
      title="Nova AutomationVersion"
      description="O backend espera automation.yaml; JSON so e aceito se o parser YAML nao estiver disponivel."
      className="max-w-4xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={submit} disabled={submitting}>Criar versao</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field>
          <Label htmlFor="automation-manifest">Manifesto YAML</Label>
          <Textarea
            id="automation-manifest"
            rows={18}
            className="font-mono text-xs"
            value={rawManifest}
            onChange={(event) => setRawManifest(event.target.value)}
          />
          {manifestError && <p className="text-xs text-destructive">{manifestError}</p>}
          <p className="text-xs text-muted-foreground">O campo automation.id deve corresponder a chave da automacao: {automationKey}.</p>
        </Field>
        <Field>
          <Label htmlFor="release-notes">Release notes</Label>
          <Textarea id="release-notes" value={releaseNotes} onChange={(event) => setReleaseNotes(event.target.value)} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field>
            <Label htmlFor="source-repo">Repositorio</Label>
            <Input id="source-repo" value={sourceRepository} onChange={(event) => setSourceRepository(event.target.value)} placeholder="owner/repo" />
          </Field>
          <Field>
            <Label htmlFor="source-branch">Branch</Label>
            <Input id="source-branch" value={sourceBranch} onChange={(event) => setSourceBranch(event.target.value)} />
          </Field>
          <Field>
            <Label htmlFor="source-tag">Tag</Label>
            <Input id="source-tag" value={sourceTag} onChange={(event) => setSourceTag(event.target.value)} />
          </Field>
          <Field>
            <Label htmlFor="source-commit">Commit SHA</Label>
            <Input id="source-commit" className="tabular" value={sourceCommitSha} onChange={(event) => setSourceCommitSha(event.target.value)} />
          </Field>
          <Field>
            <Label htmlFor="build-id">Build</Label>
            <Input id="build-id" value={buildId} onChange={(event) => setBuildId(event.target.value)} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}

function AutomationPackageUploadModal({
  version,
  open,
  onClose,
  onCompleted,
}: {
  version: AutomationVersionResponse;
  open: boolean;
  onClose: () => void;
  onCompleted: (pkg: PackageResponse) => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [session, setSession] = useState<PackageUploadResponse | null>(null);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [phase, setPhase] = useState<"idle" | "hashing" | "uploading" | "completing" | "done" | "failed">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const uploadAbort = useRef<(() => void) | null>(null);
  const idempotencyKey = useRef(createIdempotencyKey("package-upload:initiate"));

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    const dropped = event.dataTransfer.files.item(0);
    if (dropped) setFile(dropped);
  }

  async function startUpload() {
    if (!token || !file) return;
    setPhase("hashing");
    setMessage(null);
    setProgress(null);
    let uploadSession: PackageUploadResponse | null = null;
    try {
      const hash = await sha256File(file);
      if (hash.skippedReason) setMessage(hash.skippedReason);
      uploadSession = await initiatePackageUpload(
        token,
        version.id,
        {
          file_name: file.name,
          expected_size_bytes: file.size,
          expected_sha256: hash.hash,
        },
        idempotencyKey.current,
      );
      setSession(uploadSession);
      setPhase("uploading");
      const upload = putPackageFile({
        token,
        uploadUrl: uploadSession.upload_url,
        uploadSessionId: uploadSession.id,
        file,
        onProgress: setProgress,
      });
      uploadAbort.current = upload.abort;
      await upload.promise;
      uploadAbort.current = null;
      setPhase("completing");
      const pkg = await completePackageUpload(token, uploadSession.id);
      setPhase("done");
      toast({ title: pkg.status === "valid" ? "Pacote valido" : "Pacote enviado com problemas", kind: pkg.status === "valid" ? "success" : "warning" });
      idempotencyKey.current = createIdempotencyKey("package-upload:initiate");
      onCompleted(pkg);
    } catch (err) {
      if (uploadSession) {
        try {
          await abortPackageUpload(token, uploadSession.id);
        } catch {
          // Best-effort cleanup after a failed attempt.
        }
      }
      uploadAbort.current = null;
      idempotencyKey.current = createIdempotencyKey("package-upload:initiate");
      setPhase("failed");
      setMessage(err instanceof Error ? err.message : "Falha ao enviar pacote.");
    }
  }

  async function cancel() {
    uploadAbort.current?.();
    uploadAbort.current = null;
    if (token && session) {
      try {
        await abortPackageUpload(token, session.id);
      } catch {
        // Best-effort abort; the backend remains the source of truth.
      }
    }
    setPhase("idle");
    setSession(null);
    setProgress(null);
    idempotencyKey.current = createIdempotencyKey("package-upload:initiate");
  }

  const active = phase === "hashing" || phase === "uploading" || phase === "completing";
  return (
    <Modal
      open={open}
      onClose={active ? cancel : onClose}
      title={`Enviar pacote para v${version.version}`}
      description="Envio em uma unica requisicao. A conclusao so ocorre apos o endpoint /complete responder."
      className="max-w-2xl"
      footer={
        <>
          <Button variant="ghost" onClick={active ? cancel : onClose}>{active ? "Cancelar envio" : "Fechar"}</Button>
          <Button onClick={startUpload} disabled={!file || active}>
            <Upload className="h-4 w-4" /> {phase === "failed" ? "Tentar novamente" : "Enviar pacote"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <label
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 p-5 text-center hover:border-primary"
        >
          <FileArchive className="h-8 w-8 text-muted-foreground" />
          <span className="mt-2 text-sm font-medium">{file ? file.name : "Selecione ou arraste um ZIP"}</span>
          <span className="mt-1 text-xs text-muted-foreground">{file ? formatBytes(file.size) : "Pacotes grandes sao enviados por PUT unico."}</span>
          <input type="file" className="hidden" onChange={(event) => setFile(event.target.files?.item(0) ?? null)} />
        </label>
        {progress && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{phase === "completing" ? "Concluindo" : "Enviando pacote"}</span>
              <span>{progress.percent}% concluido</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${progress.percent}%` }} />
            </div>
          </div>
        )}
        {phase === "hashing" && <p className="text-sm text-muted-foreground">Calculando SHA-256 quando viavel...</p>}
        {phase === "completing" && <p className="text-sm text-muted-foreground">Validando integridade e finalizando upload...</p>}
        {message && <p className={phase === "failed" ? "text-sm text-destructive" : "text-sm text-muted-foreground"}>{message}</p>}
      </div>
    </Modal>
  );
}

function AutomationVersionDetails({ version }: { version: AutomationVersionResponse }) {
  const [tab, setTab] = useState("summary");
  const validationErrors = normalizeValidationErrors(version.validation_errors);
  return (
    <div className="space-y-5">
      <Tabs
        value={tab}
        onValueChange={setTab}
        items={[
          { value: "summary", label: "Resumo" },
          { value: "package", label: "Pacote" },
          { value: "validation", label: "Validacao", count: validationErrors.length || undefined },
          { value: "source", label: "Origem" },
          { value: "technical", label: "Tecnico" },
        ]}
      />
      {tab === "summary" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Meta label="Versao" value={`v${version.version}`} />
          <Meta label="Status" value={<AutomationVersionStatusBadge status={version.status} />} />
          <Meta label="Runtime" value={`${version.runtime_id}${version.runtime_version ? `@${version.runtime_version}` : ""}`} />
          <Meta label="RuntimeVersion ID" value={version.runtime_version_id ?? "-"} />
          <Meta label="Entrypoint" value={version.entrypoint_type} />
          <Meta label="Aplicacao" value={version.application_type} />
          <Meta label="Criada em" value={formatDateTime(version.created_at)} />
          <Meta label="Publicada em" value={formatDateTime(version.published_at)} />
        </div>
      )}
      {tab === "package" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Meta label="Package ID" value={version.package_id ?? "-"} />
          <Meta label="Bucket" value={version.artifact_bucket || "-"} />
          <Meta label="Objeto" value={<span className="tabular text-xs">{version.artifact_object_key || "-"}</span>} />
          <Meta label="Tamanho" value={formatBytes(version.artifact_size)} />
          <Meta label="SHA-256" value={<span className="tabular break-all text-xs">{version.artifact_sha256 || "-"}</span>} />
        </div>
      )}
      {tab === "validation" && <AutomationValidationErrors errors={validationErrors} />}
      {tab === "source" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Meta label="Commit" value={version.source_commit_sha ?? "-"} />
          <Meta label="Caminho" value={version.source_path ?? "-"} />
          <Meta label="Manifest ID" value={version.manifest_id ?? "-"} />
        </div>
      )}
      {tab === "technical" && <pre className="max-h-[480px] overflow-auto rounded-lg bg-muted p-4 text-xs">{JSON.stringify(version, null, 2)}</pre>}
    </div>
  );
}

function AutomationValidationErrors({ errors }: { errors: ReturnType<typeof normalizeValidationErrors> }) {
  if (errors.length === 0) {
    return <EmptyState icon={ShieldCheck} title="Sem erros de validacao" description="A ultima resposta conhecida nao trouxe erros." />;
  }
  return (
    <div className="space-y-3">
      {errors.map((error, index) => (
        <div key={`${error.code ?? "error"}-${index}`} className="rounded-lg border border-border p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={error.severity === "warning" ? "warning" : "destructive"}>{error.title}</Badge>
            {error.code && <span className="tabular text-xs text-muted-foreground">{error.code}</span>}
          </div>
          {error.field && <p className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">Campo</p>}
          {error.field && <p className="tabular text-sm">{error.field}</p>}
          <p className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">Problema</p>
          <p className="text-sm">{error.message}</p>
          {error.received && (
            <>
              <p className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">Valor recebido</p>
              <p className="tabular break-all text-sm">{error.received}</p>
            </>
          )}
          {error.expected && (
            <>
              <p className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">Valor esperado</p>
              <p className="tabular break-all text-sm">{error.expected}</p>
            </>
          )}
          <details className="mt-3">
            <summary className="cursor-pointer text-xs text-muted-foreground">Detalhes tecnicos</summary>
            <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-muted p-3 text-xs">{error.technical}</pre>
          </details>
        </div>
      ))}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
