import { PageTitle } from "@/components/shared/page-title";
import { TeamsManager } from "@/components/teams/teams-manager";

export default function TeamsPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Pessoas e acesso" title="Times" description="Quem está em cada time e o que o time pode: por categoria e por automação." /><TeamsManager /></div>;
}
