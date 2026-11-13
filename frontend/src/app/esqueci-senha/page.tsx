import { Suspense } from "react";

import { EsqueciASenha } from "@/components/auth/senha";
import { TelaDeAcesso } from "@/components/auth/tela-de-acesso";

export default function EsqueciASenhaPage() {
  return (
    <TelaDeAcesso titulo="Esqueci a senha" subtitulo="Mandamos um link para você criar uma senha nova.">
      <Suspense>
        <EsqueciASenha />
      </Suspense>
    </TelaDeAcesso>
  );
}
