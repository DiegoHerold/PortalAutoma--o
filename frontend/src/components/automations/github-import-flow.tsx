"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, Github, RotateCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import type {
  AutomationImportPreview,
  GithubDiscoveryItem,
  GithubIntegration,
  GithubRepository,
} from "@/types/automation-import";

type Step = "loading" | "connect" | "repository" | "branch" | "discover" | "review";

export function GithubImportFlow({ onImported }: { onImported: () => void }) {
  const { token } = useAuth();
  const { toast } = useToast();

  const [step, setStep] = useState<Step>("loading");
  const [integrations, setIntegrations] = useState<GithubIntegration[]>([]);
  const [integrationId, setIntegrationId] = useState<number | null>(null);
  const [repositories, setRepositories] = useState<GithubRepository[]>([]);
  const [repo, setRepo] = useState<GithubRepository | null>(null);
  const [branches, setBranches] = useState<string[]>([]);
  const [branch, setBranch] = useState("");
  const [discovered, setDiscovered] = useState<GithubDiscoveryItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previews, setPreviews] = useState<AutomationImportPreview[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadIntegrations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadIntegrations() {
    if (!token) return;
    setStep("loading");
    try {
      const list = await apiRequest<GithubIntegration[]>("/integrations/github", { token });
      setIntegrations(list);
      if (list.length === 0) {
        setStep("connect");
      } else {
        setIntegrationId(list[0].id);
        await loadRepositories(list[0].id);
      }
    } catch (err) {
      toast({ title: "Falha ao carregar integrações", description: err instanceof Error ? err.message : undefined, kind: "error" });
      setStep("connect");
    }
  }

  async function connect() {
    if (!token) return;
    setBusy(true);
    try {
      const { install_url } = await apiRequest<{ install_url: string }>("/integrations/github/connect", {
        method: "POST",
        token,
      });
      // Real top-level redirect to GitHub's installation page — same flow Vercel uses.
      window.location.href = install_url;
    } catch (err) {
      toast({ title: "Falha ao iniciar conexão com GitHub", description: err instanceof Error ? err.message : undefined, kind: "error" });
      setBusy(false);
    }
  }

  async function loadRepositories(id: number) {
    if (!token) return;
    setStep("repository");
    try {
      const repos = await apiRequest<GithubRepository[]>(`/integrations/github/${id}/repositories`, { token });
      setRepositories(repos);
    } catch (err) {
      toast({ title: "Falha ao listar repositórios", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function chooseRepository(r: GithubRepository) {
    if (!token || !integrationId) return;
    setRepo(r);
    setBranch(r.default_branch);
    setStep("branch");
    try {
      const list = await apiRequest<string[]>(
        `/integrations/github/${integrationId}/repositories/${r.owner}/${r.name}/branches`,
        { token },
      );
      setBranches(list);
    } catch (err) {
      toast({ title: "Falha ao listar branches", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  async function discover() {
    if (!token || !integrationId || !repo) return;
    setBusy(true);
    setStep("discover");
    try {
      const items = await apiRequest<GithubDiscoveryItem[]>(
        `/integrations/github/${integrationId}/repositories/${repo.owner}/${repo.name}/discover`,
        { method: "POST", token, body: JSON.stringify({ owner: repo.owner, repository: repo.name, branch }) },
      );
      setDiscovered(items);
      setSelected(new Set(items.filter((i) => i.validation_status === "valid" && !i.already_imported).map((i) => i.manifest_path)));
    } catch (err) {
      toast({ title: "Falha ao descobrir automações", description: err instanceof Error ? err.message : undefined, kind: "error" });
      setStep("branch");
    } finally {
      setBusy(false);
    }
  }

  async function importSelected() {
    if (!token || !integrationId || !repo || selected.size === 0) return;
    setBusy(true);
    try {
      const result = await apiRequest<AutomationImportPreview[]>(`/integrations/github/${integrationId}/import`, {
        method: "POST",
        token,
        body: JSON.stringify({ owner: repo.owner, repository: repo.name, branch, manifest_paths: Array.from(selected) }),
      });
      setPreviews(result);
      setStep("review");
    } catch (err) {
      toast({ title: "Falha ao empacotar automações", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function confirmOne(preview: AutomationImportPreview) {
    if (!token || !preview.staging_id) return;
    try {
      await apiRequest(`/automations/import/${preview.staging_id}/confirm`, {
        method: "POST",
        token,
        body: JSON.stringify({}),
      });
      toast({ title: "Automação importada", description: `${preview.name} v${preview.version}`, kind: "success" });
      setPreviews((prev) => prev.filter((p) => p.staging_id !== preview.staging_id));
      onImported();
    } catch (err) {
      toast({ title: "Falha ao confirmar", description: err instanceof Error ? err.message : undefined, kind: "error" });
    }
  }

  if (step === "loading") {
    return <Skeleton className="h-40 rounded-lg" />;
  }

  if (step === "connect") {
    return (
      <EmptyState
        icon={Github}
        title="Nenhuma conta GitHub conectada"
        description="Conecte a conta/organização GitHub que contém o repositório biason-automations para descobrir e importar automações diretamente de lá."
        action={
          <Button onClick={connect} disabled={busy}>
            <Github className="h-4 w-4" /> {busy ? "Redirecionando..." : "Conectar GitHub"}
          </Button>
        }
      />
    );
  }

  if (step === "repository") {
    return (
      <div className="space-y-3">
        {integrations.length > 1 && (
          <Select
            value={integrationId ?? ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setIntegrationId(id);
              void loadRepositories(id);
            }}
          >
            {integrations.map((i) => (
              <option key={i.id} value={i.id}>
                {i.account_login}
              </option>
            ))}
          </Select>
        )}
        {repositories.length === 0 ? (
          <EmptyState title="Nenhum repositório acessível" description="Verifique se a instalação do App inclui o repositório desejado." />
        ) : (
          <ul className="max-h-80 divide-y divide-border overflow-y-auto rounded-lg border border-border">
            {repositories.map((r) => (
              <li key={r.id}>
                <button
                  onClick={() => void chooseRepository(r)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left text-sm hover:bg-accent"
                >
                  <span>{r.full_name}</span>
                  {r.private && <Badge tone="neutral">privado</Badge>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (step === "branch") {
    return (
      <div className="space-y-4">
        <BackButton onClick={() => setStep("repository")} label={repo?.full_name} />
        <div>
          <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Branch</label>
          <Select value={branch} onChange={(e) => setBranch(e.target.value)}>
            {branches.length === 0 && repo && <option value={repo.default_branch}>{repo.default_branch}</option>}
            {branches.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex justify-end">
          <Button onClick={discover} disabled={busy || !branch}>
            {busy ? "Buscando..." : "Buscar automações"}
          </Button>
        </div>
      </div>
    );
  }

  if (step === "discover") {
    if (busy) return <Skeleton className="h-40 rounded-lg" />;
    return (
      <div className="space-y-4">
        <BackButton onClick={() => setStep("branch")} label={`${repo?.full_name} @ ${branch}`} />
        {discovered.length === 0 ? (
          <EmptyState
            title="Nenhum automation.yaml encontrado"
            description="Verifique automation-workspace.yaml na raiz do repositório e os caminhos configurados."
          />
        ) : (
          <>
            <ul className="max-h-96 space-y-2 overflow-y-auto">
              {discovered.map((item) => {
                const valid = item.validation_status === "valid";
                const disabled = !valid || item.already_imported;
                const checked = selected.has(item.manifest_path);
                return (
                  <li
                    key={item.manifest_path}
                    className={`rounded-lg border p-3 ${checked ? "border-primary bg-primary/5" : "border-border"}`}
                  >
                    <label className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={checked}
                        disabled={disabled}
                        onChange={(e) => {
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (e.target.checked) next.add(item.manifest_path);
                            else next.delete(item.manifest_path);
                            return next;
                          });
                        }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{item.name || item.manifest_path}</span>
                          <Badge tone={valid ? "success" : "destructive"}>{valid ? "Válido" : "Inválido"}</Badge>
                        </div>
                        <p className="tabular truncate text-xs text-muted-foreground">
                          {item.key} · v{item.version} · {item.path}
                        </p>
                        {item.already_imported && (
                          <p className="mt-1 flex items-center gap-1 text-xs text-warning">
                            <AlertTriangle className="h-3 w-3" /> Já importado
                          </p>
                        )}
                        {item.errors.length > 0 && (
                          <ul className="mt-1 space-y-0.5 text-xs text-destructive">
                            {item.errors.map((e, i) => (
                              <li key={i}>{e}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={discover}>
                <RotateCw className="h-3.5 w-3.5" /> Atualizar
              </Button>
              <Button onClick={importSelected} disabled={busy || selected.size === 0}>
                {busy ? "Empacotando..." : `Importar ${selected.size} selecionada(s)`}
              </Button>
            </div>
          </>
        )}
      </div>
    );
  }

  // step === "review"
  return (
    <div className="space-y-3">
      {previews.length === 0 ? (
        <EmptyState title="Tudo importado" description="Nenhum item pendente de confirmação." />
      ) : (
        previews.map((p) => {
          const valid = p.validation_status === "valid" && !p.already_imported;
          return (
            <div key={p.manifest_path} className="rounded-lg border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{p.name}</p>
                  <p className="tabular text-xs text-muted-foreground">{p.key} · v{p.version}</p>
                </div>
                <Badge tone={valid ? "success" : "destructive"}>{valid ? "Pronto" : "Inválido"}</Badge>
              </div>
              {p.errors.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-destructive">
                  {p.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
              {valid && (
                <div className="mt-3 flex justify-end">
                  <Button size="sm" onClick={() => confirmOne(p)}>
                    Confirmar importação
                  </Button>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

function BackButton({ onClick, label }: { onClick: () => void; label?: string }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-3.5 w-3.5" /> {label ?? "Voltar"}
    </button>
  );
}
