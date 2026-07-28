"use client";

import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileArchive, Upload } from "lucide-react";

import { AutomationForm, emptyAutomationForm, type AutomationFormState } from "@/components/automations/automation-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest, apiUpload } from "@/lib/api";
import { applyImportedAutomationConfig, slugify } from "@/lib/automation-config";
import type { AutomationImportPreview } from "@/types/automation-import";
import type { Category } from "@/types/category";
import type { Worker } from "@/types/worker";

export function ZipImportFlow({
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<AutomationImportPreview | null>(null);
  const [confirming, setConfirming] = useState(false);

  async function handleFile(file: File) {
    if (!token) return;
    setUploading(true);
    setPreview(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await apiUpload<AutomationImportPreview>("/automations/import/upload", form, token);
      setPreview(result);
    } catch (err) {
      toast({ title: "Falha ao validar pacote", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setUploading(false);
    }
  }

  async function confirm(form: AutomationFormState) {
    if (!token || !preview?.staging_id) return;
    setConfirming(true);
    try {
      await applyImportedAutomationConfig(token, preview.staging_id, form);
      toast({ title: "Automação importada", description: `${preview.name} v${preview.version}`, kind: "success" });
      setPreview(null);
      onImported();
    } catch (err) {
      toast({ title: "Falha ao criar automação", description: err instanceof Error ? err.message : undefined, kind: "error" });
    } finally {
      setConfirming(false);
    }
  }

  async function discard() {
    if (!token || !preview?.staging_id) {
      setPreview(null);
      return;
    }
    try {
      await apiRequest(`/automations/import/${preview.staging_id}`, { method: "DELETE", token });
    } catch {
      /* best effort */
    } finally {
      setPreview(null);
    }
  }

  if (preview) {
    const valid = preview.validation_status === "valid";
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium">{preview.name || preview.key}</p>
              <p className="tabular text-xs text-muted-foreground">
                {preview.key} · v{preview.version} · runtime {preview.runtime_id}
              </p>
              {preview.description && <p className="mt-1 text-sm text-muted-foreground">{preview.description}</p>}
            </div>
            <Badge tone={valid ? "success" : "destructive"}>{valid ? "Válido" : "Inválido"}</Badge>
          </div>

          {preview.already_imported && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-warning">
              <AlertTriangle className="h-3.5 w-3.5" /> Esta versão já foi importada anteriormente.
            </p>
          )}

          {preview.errors.length > 0 && (
            <ul className="mt-3 space-y-1 rounded-md bg-destructive/5 p-3 text-xs text-destructive">
              {preview.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}

          <p className="tabular mt-3 text-xs text-muted-foreground">
            Pacote: {(preview.package_size / 1024).toFixed(1)} KB · sha256 {preview.package_sha256.slice(0, 12)}...
          </p>
        </div>

        {valid && !preview.already_imported && (
          <AutomationForm
            key={preview.staging_id ?? preview.key}
            categories={categories}
            workers={workers}
            initial={formFromPreview(preview, categories)}
            onSubmit={confirm}
            submitting={confirming}
            submitLabel="Criar automação"
          />
        )}

        <div className="flex justify-start gap-2">
          <Button variant="outline" onClick={discard}>
            Cancelar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-12 text-center"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const file = e.dataTransfer.files?.[0];
        if (file) void handleFile(file);
      }}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <FileArchive className="h-6 w-6" />
      </div>
      <div>
        <p className="font-medium">Arraste um pacote .zip aqui</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Deve conter automation.yaml na raiz do pacote, ou dentro de uma única pasta.
        </p>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".zip"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
        }}
      />
      <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
        <Upload className="h-4 w-4" /> {uploading ? "Enviando..." : "Selecionar arquivo"}
      </Button>
      {uploading && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <CheckCircle2 className="h-3.5 w-3.5 animate-pulse" /> Validando manifesto e empacotando...
        </p>
      )}
    </div>
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
