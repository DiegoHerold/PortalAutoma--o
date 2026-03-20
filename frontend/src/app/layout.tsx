import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@/app/globals.css";
import { AuthProvider } from "@/components/auth/auth-provider";
import { APP_NAME } from "@/lib/constants";

export const metadata: Metadata = {
  title: APP_NAME,
  description: "Portal de automacoes com painel operacional, filas e workers distribuidos.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
