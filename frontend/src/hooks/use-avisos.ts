"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";
import { abrirStream } from "@/lib/stream";

/**
 * Avisos em tempo real (SSE com o token no cabeçalho). Vários avisos seguidos viram uma
 * chamada só de ``aoMudar``. Devolve se a conexão ao vivo está de pé.
 */
export function useAvisos(caminho: string | null, aoMudar: () => void, esperaMs = 500): boolean {
  const { token } = useAuth();
  const [aoVivo, setAoVivo] = useState(false);
  const agendado = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callback = useRef(aoMudar);
  callback.current = aoMudar;

  useEffect(() => {
    if (!token || !caminho) return;
    const fechar = abrirStream(
      caminho,
      token,
      (evento) => {
        if (evento.evento !== "mudou" || agendado.current) return;
        agendado.current = setTimeout(() => {
          agendado.current = null;
          callback.current();
        }, esperaMs);
      },
      { aoMudarConexao: setAoVivo },
    );
    return () => {
      fechar();
      if (agendado.current) clearTimeout(agendado.current);
      agendado.current = null;
    };
  }, [caminho, token, esperaMs]);

  return aoVivo;
}

/** Segundos passados desde ``desde`` (ISO), andando a cada segundo enquanto ``ativo``. */
export function useSegundosDesde(desde: string | null | undefined, ativo = true): number {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    if (!ativo) return;
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [ativo]);
  if (!desde) return 0;
  return Math.max(0, Math.floor((agora - new Date(desde).getTime()) / 1000));
}
