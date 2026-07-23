"use client";

import { useState } from "react";
import { ArrowLeft, FileArchive, Github, PencilLine } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { AutomationForm, type AutomationFormState } from "@/components/automations/automation-form";
import { ZipImportFlow } from "@/components/automations/zip-import-flow";
import { GithubImportFlow } from "@/components/automations/github-import-flow";
import type { Category } from "@/types/category";

type Mode = "choose" | "manual" | "zip" | "github";

export function NewAutomationDialog({
  open,
  onClose,
  categories,
  onManualSubmit,
  submitting,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  categories: Category[];
  onManualSubmit: (form: AutomationFormState) => Promise<void>;
  submitting: boolean;
  onImported: () => void;
}) {
  const [mode, setMode] = useState<Mode>("choose");

  function handleClose() {
    setMode("choose");
    onClose();
  }

  const titles: Record<Mode, { title: string; description: string }> = {
    choose: { title: "Nova automação", description: "Como você quer adicionar esta automação?" },
    manual: { title: "Cadastro manual", description: "Defina metadados e um pacote existente manualmente." },
    zip: { title: "Enviar pacote ZIP", description: "Envie um pacote com automation.yaml para validação e importação." },
    github: { title: "Importar do GitHub", description: "Conecte um repositório e selecione as automações a importar." },
  };

  return (
    <Modal open={open} onClose={handleClose} title={titles[mode].title} description={titles[mode].description} className="max-w-2xl">
      {mode !== "choose" && (
        <button
          onClick={() => setMode("choose")}
          className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Escolher outro método
        </button>
      )}

      {mode === "choose" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <ChoiceCard
            icon={Github}
            title="Importar do GitHub"
            description="Descobre automation.yaml em um repositório conectado."
            onClick={() => setMode("github")}
          />
          <ChoiceCard
            icon={FileArchive}
            title="Enviar pacote ZIP"
            description="Envie manualmente um pacote com automation.yaml."
            onClick={() => setMode("zip")}
          />
          <ChoiceCard
            icon={PencilLine}
            title="Formulário manual"
            description="Cadastre metadados apontando para um pacote existente."
            onClick={() => setMode("manual")}
          />
        </div>
      )}

      {mode === "manual" && (
        <AutomationForm
          categories={categories}
          onSubmit={onManualSubmit}
          submitting={submitting}
          submitLabel="Criar automação"
        />
      )}

      {mode === "zip" && (
        <ZipImportFlow
          categories={categories}
          onImported={() => {
            onImported();
            handleClose();
          }}
        />
      )}

      {mode === "github" && (
        <GithubImportFlow
          onImported={() => {
            onImported();
          }}
        />
      )}
    </Modal>
  );
}

function ChoiceCard({
  icon: Icon,
  title,
  description,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-start gap-2 rounded-lg border border-border p-4 text-left transition-colors hover:border-primary hover:bg-primary/5"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-md bg-muted text-foreground">
        <Icon className="h-4.5 w-4.5" />
      </span>
      <span className="text-sm font-medium">{title}</span>
      <span className="text-xs text-muted-foreground">{description}</span>
    </button>
  );
}
