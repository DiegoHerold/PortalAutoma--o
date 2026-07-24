"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FolderGit2,
  GitBranch,
  Github,
  PackageCheck,
  RotateCw,
  Settings2,
} from "lucide-react";

import { AutomationForm, emptyAutomationForm, type AutomationFormState } from "@/components/automations/automation-form";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";
import { applyImportedAutomationConfig, slugify } from "@/lib/automation-config";
import type {
  AutomationImportPreview,
  GithubDiscoveryItem,
  GithubIntegration,
  GithubRepository,
} from "@/types/automation-import";
import type { Category } from "@/types/category";
import type { Worker } from "@/types/worker";

type Step = "loading" | "connect" | "repository" | "branch" | "projects" | "configure" | "done";

export function GithubImportFlow({
  categories,
  workers,
  onImported,
}: {
  categories: Category[];
  workers: Worker[];
  onImported: () => void;
}) {
  const { token } = useAuth();
  const { toast } = useToast();

  const [step, setStep] = useState<Step>("loading");
  const [integrations, setIntegrations] = useState<GithubIntegration[]>([]);
  const [integrationId, setIntegrationId] = useState<number | null>(null);
  const [repositories, setRepositories] = useState<GithubRepository[]>([]);
  const [repo, setRepo] = useState<GithubRepository | null>(null);
  const [branches, setBranches] = useState<string[]>([]);
  const [branch, setBranch] = useState("");
  const [projects, setProjects] = useState<GithubDiscoveryItem[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [preview, setPreview] = useState<AutomationImportPreview | null>(null);

  const [repositoriesLoading, setRepositoriesLoading] = useState(false);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadIntegrations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedProject = useMemo(
    () => projects.find((project) => project.manifest_path === selectedPath) ?? null,
    [projects, selectedPath],
  );

  async function loadIntegrations() {
    if (!token) return;
    setStep("loading");
    try {
      const list = await apiRequest<GithubIntegration[]>("/integrations/github", { token });
      setIntegrations(list);
      if (list.length === 0) {
        setStep("connect");
        return;
      }
      setIntegrationId(list[0].id);
      await loadRepositories(list[0].id);
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
      window.location.href = install_url;
    } catch (err) {
      toast({ title: "Falha ao iniciar conexão com GitHub", description: err instanceof Error ? err.message : undefined, kind: "error" });
      setBusy(false);
    }
  }

  async function loadRepositories(id: number) {
    if (!token) return;
    setRepositories([]);
    setRepo(null);
    setBranches([]);
    setBranch("");
    setProjects([]);
    setSelectedPath(null);
    setPreview(null);
    setStep("repository");
    setRepositoriesLoading(true);
    try {
      const repos = await apiRequest<GithubRepository[]>(`/integrations/github/${id}/repositories`, { token });
      setRepositories(repos);
    } catch (err) {
      toast({ title: "Falha ao listar repositórios", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setRepositoriesLoading(false);
    }
  }

  async function chooseRepository(repository: GithubRepository) {
    if (!token || !integrationId) return;
    setRepo(repository);
    setBranch(repository.default_branch);
    setBranches([]);
    setProjects([]);
    setSelectedPath(null);
    setPreview(null);
    setStep("branch");
    setBranchesLoading(true);
    try {
      const list = await apiRequest<string[]>(
        `/integrations/github/${integrationId}/repositories/${repository.owner}/${repository.name}/branches`,
        { token },
      );
      setBranches(list.length > 0 ? list : [repository.default_branch]);
    } catch (err) {
      toast({ title: "Falha ao listar branches", description: err instanceof Error ? err.message : undefined, kind: "error" });
      setBranches([repository.default_branch]);
    } finally {
      setBranchesLoading(false);
    }
  }

  async function discoverProjects() {
    if (!token || !integrationId || !repo || !branch) return;
    setProjects([]);
    setSelectedPath(null);
    setPreview(null);
    setStep("projects");
    setProjectsLoading(true);
    try {
      const items = await apiRequest<GithubDiscoveryItem[]>(
        `/integrations/github/${integrationId}/repositories/${repo.owner}/${repo.name}/discover`,
        { method: "POST", token, body: JSON.stringify({ owner: repo.owner, repository: repo.name, branch }) },
      );
      setProjects(items);
      setSelectedPath(items.find((item) => item.validation_status === "valid" && !item.already_imported)?.manifest_path ?? null);
    } catch (err) {
      toast({ title: "Falha ao descobrir automações", description: err instanceof Error ? err.message : undefined, kind: "error" });
      setStep("branch");
    } finally {
      setProjectsLoading(false);
    }
  }

  async function prepareSelectedProject() {
    if (!token || !integrationId || !repo || !selectedProject) return;
    setBusy(true);
    try {
      const result = await apiRequest<AutomationImportPreview[]>(`/integrations/github/${integrationId}/import`, {
        method: "POST",
        token,
        body: JSON.stringify({
          owner: repo.owner,
          repository: repo.name,
          branch,
          manifest_paths: [selectedProject.manifest_path],
        }),
      });
      const nextPreview = result[0];
      if (!nextPreview) {
        toast({ title: "Nenhum pacote retornado pelo GitHub", kind: "error" });
        return;
      }
      setPreview(nextPreview);
      setStep("configure");
    } catch (err) {
      toast({ title: "Falha ao preparar automação", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function confirm(form: AutomationFormState) {
    if (!token || !preview?.staging_id) return;
    setBusy(true);
    try {
      await applyImportedAutomationConfig(token, preview.staging_id, form);
      toast({ title: "Automação criada", description: `${preview.name} v${preview.version}`, kind: "success" });
      onImported();
      setStep("done");
    } catch (err) {
      toast({ title: "Falha ao criar automação", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  if (step === "loading") {
    return (
      <div className="space-y-4">
        <WizardSteps current="repository" />
        <Skeleton className="h-44 rounded-lg" />
      </div>
    );
  }

  if (step === "connect") {
    return (
      <EmptyState
        icon={Github}
        title="Nenhuma conta GitHub conectada"
        description="Conecte a conta ou organização GitHub que contém os repositórios das automações."
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
      <div className="space-y-4">
        <WizardSteps current="repository" />
        {integrations.length > 1 && (
          <Select
            value={integrationId ?? ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setIntegrationId(id);
              void loadRepositories(id);
            }}
          >
            {integrations.map((integration) => (
              <option key={integration.id} value={integration.id}>
                {integration.account_login}
              </option>
            ))}
          </Select>
        )}

        {repositoriesLoading ? (
          <Skeleton className="h-56 rounded-lg" />
        ) : repositories.length === 0 ? (
          <EmptyState
            icon={FolderGit2}
            title="Nenhum repositório acessível"
            description="Verifique se a instalação do App inclui o repositório desejado."
            action={
              integrationId ? (
                <Button variant="outline" onClick={() => void loadRepositories(integrationId)}>
                  <RotateCw className="h-4 w-4" /> Atualizar
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="max-h-80 divide-y divide-border overflow-y-auto rounded-lg border border-border">
            {repositories.map((repository) => (
              <li key={repository.id}>
                <button
                  onClick={() => void chooseRepository(repository)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-accent"
                >
                  <span className="min-w-0 truncate font-medium">{repository.full_name}</span>
                  {repository.private && <Badge tone="neutral">privado</Badge>}
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
        <WizardSteps current="branch" />
        <BackButton onClick={() => setStep("repository")} label={repo?.full_name} />
        <div className="rounded-lg border border-border p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium">
            <GitBranch className="h-4 w-4 text-muted-foreground" /> Branch do repositório
          </div>
          {branchesLoading ? (
            <Skeleton className="h-10 rounded-md" />
          ) : (
            <Select value={branch} onChange={(e) => setBranch(e.target.value)}>
              {branches.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          )}
        </div>
        <div className="flex justify-end">
          <Button onClick={discoverProjects} disabled={branchesLoading || !branch}>
            Carregar projetos
          </Button>
        </div>
      </div>
    );
  }

  if (step === "projects") {
    return (
      <div className="space-y-4">
        <WizardSteps current="projects" />
        <BackButton onClick={() => setStep("branch")} label={`${repo?.full_name} @ ${branch}`} />

        {projectsLoading ? (
          <Skeleton className="h-72 rounded-lg" />
        ) : projects.length === 0 ? (
          <EmptyState
            icon={PackageCheck}
            title="Nenhum automation.yaml encontrado"
            description="Verifique o automation-workspace.yaml na raiz do repositório e os caminhos configurados."
            action={
              <Button variant="outline" onClick={discoverProjects}>
                <RotateCw className="h-4 w-4" /> Recarregar
              </Button>
            }
          />
        ) : (
          <>
            <ul className="max-h-96 space-y-2 overflow-y-auto">
              {projects.map((project) => {
                const valid = project.validation_status === "valid";
                const disabled = !valid || project.already_imported;
                const checked = selectedPath === project.manifest_path;
                return (
                  <li
                    key={project.manifest_path}
                    className={`rounded-lg border p-3 ${
                      checked ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                    }`}
                  >
                    <label className={`flex items-start gap-3 ${disabled ? "opacity-70" : "cursor-pointer"}`}>
                      <input
                        type="radio"
                        name="github-project"
                        className="mt-1 h-4 w-4 border-input accent-primary"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => setSelectedPath(project.manifest_path)}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-medium">{project.name || project.manifest_path}</span>
                          <Badge tone={valid ? "success" : "destructive"}>{valid ? "Válido" : "Inválido"}</Badge>
                        </div>
                        <p className="tabular truncate text-xs text-muted-foreground">
                          {project.key} · v{project.version} · {project.path}
                        </p>
                        {project.already_imported && (
                          <p className="mt-1 flex items-center gap-1 text-xs text-warning">
                            <AlertTriangle className="h-3 w-3" /> Já importado
                          </p>
                        )}
                        {project.errors.length > 0 && (
                          <ul className="mt-1 space-y-0.5 text-xs text-destructive">
                            {project.errors.map((error, i) => (
                              <li key={i}>{error}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
            <div className="flex justify-between gap-2">
              <Button variant="outline" size="sm" onClick={discoverProjects}>
                <RotateCw className="h-3.5 w-3.5" /> Atualizar
              </Button>
              <Button onClick={prepareSelectedProject} disabled={busy || !selectedProject}>
                {busy ? "Preparando..." : "Configurar automação"}
              </Button>
            </div>
          </>
        )}
      </div>
    );
  }

  if (step === "configure" && preview) {
    const valid = preview.validation_status === "valid" && !preview.already_imported;
    return (
      <div className="space-y-4">
        <WizardSteps current="configure" />
        <BackButton onClick={() => setStep("projects")} label={preview.name || preview.key} />
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium">{preview.name || preview.key}</p>
              <p className="tabular text-xs text-muted-foreground">
                {preview.key} · v{preview.version} · {repo?.full_name} @ {branch}
              </p>
              {preview.description && <p className="mt-1 text-sm text-muted-foreground">{preview.description}</p>}
            </div>
            <Badge tone={valid ? "success" : "destructive"}>{valid ? "Pacote pronto" : "Inválido"}</Badge>
          </div>
        </div>
        {valid ? (
          <AutomationForm
            key={preview.staging_id ?? preview.key}
            categories={categories}
            workers={workers}
            initial={formFromPreview(preview, categories)}
            onSubmit={confirm}
            submitting={busy}
            submitLabel="Criar automação"
          />
        ) : (
          <EmptyState title="Projeto inválido" description="Volte, escolha outro projeto ou corrija o manifesto no repositório." />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <WizardSteps current="done" />
      <EmptyState
        icon={CheckCircle2}
        title="Automação criada"
        description="A automação já foi anexada ao projeto escolhido e recebeu as configurações de execução."
        action={
          <Button
            variant="outline"
            onClick={() => {
              setPreview(null);
              setProjects([]);
              setSelectedPath(null);
              setStep("repository");
            }}
          >
            Importar outra
          </Button>
        }
      />
    </div>
  );
}

function WizardSteps({ current }: { current: Step }) {
  const steps: { key: Step; label: string; icon: ComponentType<{ className?: string }> }[] = [
    { key: "repository", label: "Repositório", icon: FolderGit2 },
    { key: "branch", label: "Branch", icon: GitBranch },
    { key: "projects", label: "Projetos", icon: PackageCheck },
    { key: "configure", label: "Configurar", icon: Settings2 },
  ];
  const foundIndex = steps.findIndex((item) => item.key === current);
  const currentIndex = current === "done" ? steps.length : Math.max(0, foundIndex);

  return (
    <ol className="grid gap-2 sm:grid-cols-4">
      {steps.map((item, index) => {
        const Icon = item.icon;
        const active = index === currentIndex;
        const done = index < currentIndex || current === "done";
        return (
          <li
            key={item.key}
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium ${
              active
                ? "border-primary bg-primary/5 text-primary"
                : done
                  ? "border-success/30 bg-success/5 text-success"
                  : "border-border text-muted-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="truncate">{item.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function BackButton({ onClick, label }: { onClick: () => void; label?: string }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-3.5 w-3.5" /> {label ?? "Voltar"}
    </button>
  );
}

function formFromPreview(preview: AutomationImportPreview, categories: Category[]): AutomationFormState {
  const categoryId =
    categories.find((category) => category.name.toLowerCase() === preview.category?.toLowerCase())?.id ?? categories[0]?.id;

  return {
    ...emptyAutomationForm,
    name: preview.name || preview.key,
    slug: slugify(preview.name || preview.key),
    description: preview.description ?? "",
    category_id: categoryId ? String(categoryId) : "",
  };
}
