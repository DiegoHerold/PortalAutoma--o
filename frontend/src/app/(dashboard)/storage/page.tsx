import { StorageManager } from "@/components/storage/storage-manager";
import { PageTitle } from "@/components/shared/page-title";

export default function StoragePage() {
  return <div className="space-y-6"><PageTitle eyebrow="Infraestrutura" title="Armazenamento" description="Localize, inspecione e baixe artefatos gerados pelas execuções autorizadas." /><StorageManager /></div>;
}
