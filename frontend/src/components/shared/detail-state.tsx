"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { LoadingState } from "@/components/shared/loading-state";
import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";

type DetailStateProps<T> = {
  path: string;
  render: (data: T) => ReactNode;
  loadingLabel: string;
};

export function DetailState<T>({ path, render, loadingLabel }: DetailStateProps<T>) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiRequest<T>(path, { token })
      .then(setData)
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : "Falha ao carregar detalhes.");
      })
      .finally(() => setLoading(false));
  }, [path, token]);

  if (loading) return <LoadingState label={loadingLabel} />;
  if (error || !data) return <div className="rounded-3xl bg-white/80 p-6 shadow-sm text-rose-600">{error ?? "Detalhe nao encontrado."}</div>;
  return <>{render(data)}</>;
}
