"use client";

import { useEffect, useState } from "react";
import { ImageOff } from "lucide-react";

import { useAuth } from "@/hooks/use-auth";
import { API_BASE_URL } from "@/lib/constants";
import { cn } from "@/lib/utils";

type Tamanho = "miniatura" | "media" | "cheia";

/*
 * A imagem do passo só sai da API com o token no cabeçalho e a permissão de telas e logs.
 * Não existe URL pública: o navegador recebe os bytes e mostra por um `blob:` local.
 * A mesma imagem nunca muda, então fica guardada na memória da aba.
 */
const guardadas = new Map<string, Promise<string>>();
const LIMITE = 300;

function buscar(execucao: string, imagem: string, tamanho: Tamanho, token: string): Promise<string> {
  const chave = `${execucao}/${imagem}/${tamanho}`;
  const existente = guardadas.get(chave);
  if (existente) return existente;
  const pedido = fetch(`${API_BASE_URL}/execucoes/${encodeURIComponent(execucao)}/imagens/${encodeURIComponent(imagem)}?tamanho=${tamanho}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(async (resposta) => {
    if (!resposta.ok) throw new Error(String(resposta.status));
    return URL.createObjectURL(await resposta.blob());
  });
  pedido.catch(() => guardadas.delete(chave));
  guardadas.set(chave, pedido);
  if (guardadas.size > LIMITE) {
    const [antiga] = guardadas.keys();
    const promessa = guardadas.get(antiga);
    guardadas.delete(antiga);
    void promessa?.then((url) => URL.revokeObjectURL(url)).catch(() => undefined);
  }
  return pedido;
}

export function ImagemDoPasso({
  execucao,
  imagem,
  tamanho,
  alt,
  className,
  recusada,
}: {
  execucao: string;
  imagem: string | null;
  tamanho: Tamanho;
  alt: string;
  className?: string;
  /** Motivo, quando o portal recusou a imagem (vazia, corrompida...). */
  recusada?: string | null;
}) {
  const { token } = useAuth();
  const [url, setUrl] = useState<string | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let vivo = true;
    setFalhou(false);
    if (!imagem || !token || recusada) {
      setUrl(null);
      return;
    }
    buscar(execucao, imagem, tamanho, token)
      .then((u) => vivo && setUrl(u))
      .catch(() => vivo && setFalhou(true));
    return () => {
      vivo = false;
    };
  }, [execucao, imagem, tamanho, token, recusada]);

  if (!imagem || recusada || falhou) {
    return (
      <div className={cn("flex flex-col items-center justify-center gap-1 bg-muted text-center text-xs text-muted-foreground", className)}>
        <ImageOff className="h-5 w-5" />
        <span>{recusada ? `Imagem recusada: ${recusada}` : !imagem ? "Passo sem imagem" : "Imagem indisponível"}</span>
      </div>
    );
  }
  if (!url) return <div className={cn("skeleton", className)} aria-label="Carregando imagem" />;
  // eslint-disable-next-line @next/next/no-img-element -- blob: local, o next/image não se aplica
  return <img src={url} alt={alt} className={cn("object-contain", className)} draggable={false} />;
}
