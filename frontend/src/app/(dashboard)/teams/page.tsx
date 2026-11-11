import { PageTitle } from "@/components/shared/page-title";
import { TeamsManager } from "@/components/teams/teams-manager";

export default function TeamsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Pessoas e acesso" title="Times" description="Times organizados por contexto e metadados operacionais." /><TeamsManager /></div>;
}
