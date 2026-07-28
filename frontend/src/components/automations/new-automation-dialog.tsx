"use client";

import { useState } from "react";
import { ArrowLeft, FileArchive, Github } from "lucide-react";

import { Modal } from "@/components/ui/modal";
import { ZipImportFlow } from "@/components/automations/zip-import-flow";
import { GithubImportFlow } from "@/components/automations/github-import-flow";
import type { Category } from "@/types/category";
import type { Worker } from "@/types/worker";

type Mode = "choose" | "zip" | "github";

export function NewAutomationDialog({
  open,
  onClose,
  categories,
  workers,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  categories: Category[];
  workers: Worker[];
  onImported: () => void;
}) {
  const [mode, setMode] = useState<Mode>("choose");

  function handleClose() {
    setMode("choose");
    onClose();
  }

  const titles: Record<Mode, { title: string; description: string }> = {
    choose: {
      title: "Nova automação",
      description: "Toda automação precisa de um pacote executável — importe do GitHub ou envie um ZIP.",
    },
    zip: { title: "Enviar pacote ZIP", description: "Envie um pacote com automation.yaml para validação e importação." },
    github: { title: "Importar do GitHub", description: "Conecte um repositório e selecione as automações a importar." },
  };

  return (
    <Modal open={open} onClose={handleClose} title={titles[mode].title} description={titles[mode].description} className="max-w-3xl">
      {mode !== "choose" && (
        <button
          onClick={() => setMode("choose")}
          className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Escolher outro método
        </button>
      )}

      {mode === "choose" && (
        <div className="grid gap-3 sm:grid-cols-2">
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
        </div>
      )}

      {mode === "zip" && (
        <ZipImportFlow
          categories={categories}
          workers={workers}
          onImported={() => {
            onImported();
            handleClose();
          }}
        />
      )}

      {mode === "github" && (
        <GithubImportFlow
          categories={categories}
          workers={workers}
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
