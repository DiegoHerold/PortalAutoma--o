import type { Metadata } from "next";

import { PageTitle } from "@/components/shared/page-title";
import { CategoriesManager } from "@/components/categories/categories-manager";

export const metadata: Metadata = { title: "Categorias" };

export default function CategoriesPage() {
  return (
    <div className="space-y-6">
      <PageTitle eyebrow="Governança" title="Categorias" description="Organize automações por área e controle permissões por ação." />
      <CategoriesManager />
    </div>
  );
}
