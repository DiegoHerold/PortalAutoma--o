"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

export function DetailJson({ data }: { data: unknown }) {
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(data, null, 2);

  async function copy() {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-[hsl(224_28%_7%)]">
      <button
        onClick={copy}
        className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-md bg-white/10 px-2 py-1 text-xs text-slate-200 hover:bg-white/20"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? "Copiado" : "Copiar"}
      </button>
      <pre className="tabular overflow-auto p-5 text-xs leading-relaxed text-slate-100">{json}</pre>
    </div>
  );
}
