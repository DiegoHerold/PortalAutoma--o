import { RetentionPoliciesView } from "@/components/governance/retention-policies-view";
import { PageTitle } from "@/components/shared/page-title";

export default function GovernanceRetentionPage() {
  return <div className="space-y-6"><PageTitle eyebrow="Governança" title="Retenção" description="Políticas por tipo de recurso, prazos e retenção legal." /><RetentionPoliciesView /></div>;
}
