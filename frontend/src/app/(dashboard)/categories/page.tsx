import { PageTitle } from "@/components/shared/page-title";
import { CategoriesManager } from "@/components/categories/categories-manager";

export default function CategoriesPage() {
  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Governanca"
        title="Categorias"
        description="Organize automacoes por area e aplique regras finas de permissao por acao."
      />
      <CategoriesManager />
    </div>
  );
}
