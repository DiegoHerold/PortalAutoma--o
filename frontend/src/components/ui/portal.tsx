"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Leva o conteúdo para o fim do <body>. Janelas e fundos borrados precisam ficar
 * fora da página: dentro dela, o borrão não alcança o cabeçalho fixo do topo.
 */
export function Portal({ children }: { children: ReactNode }) {
  const [pronto, setPronto] = useState(false);
  useEffect(() => setPronto(true), []);
  return pronto ? createPortal(children, document.body) : null;
}
