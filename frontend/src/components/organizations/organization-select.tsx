import { Select } from "@/components/ui/input";
import type { OrganizationResponse } from "@/types/access";

export function OrganizationSelect({ organizations, value, onChange, includeAll = false, id, disabled = false }: { organizations: OrganizationResponse[]; value: string; onChange: (value: string) => void; includeAll?: boolean; id: string; disabled?: boolean }) {
  return <Select id={id} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>{includeAll && <option value="">Todas as organizacoes</option>}{!includeAll && <option value="">Selecione uma organizacao</option>}{organizations.map((organization) => <option key={organization.id} value={organization.id}>{organization.name} ({organization.key})</option>)}</Select>;
}
