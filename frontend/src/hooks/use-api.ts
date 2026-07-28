"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";
import { apiRequest } from "@/lib/api";

type Options = {
  /** Polling interval in ms. When set, data refetches on this cadence. */
  pollMs?: number;
  enabled?: boolean;
};

/**
 * Client-side data fetching with loading/error state, manual refetch and optional polling.
 * The app authenticates with a bearer token held client-side, so data is fetched here
 * rather than in Server Components.
 */
export function useApi<T>(path: string | null, { pollMs, enabled = true }: Options = {}) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const load = useCallback(
    async (silent = false) => {
      if (!token || !path || !enabled) return;
      if (!silent) setLoading(true);
      try {
        const result = await apiRequest<T>(path, { token });
        if (mounted.current) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (mounted.current) setError(err instanceof Error ? err.message : "Falha ao carregar dados.");
      } finally {
        if (mounted.current) setLoading(false);
      }
    },
    [token, path, enabled],
  );

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  useEffect(() => {
    if (!pollMs || !enabled) return;
    const id = setInterval(() => void load(true), pollMs);
    return () => clearInterval(id);
  }, [pollMs, enabled, load]);

  return { data, loading, error, refetch: () => load(false), mutate: setData };
}
