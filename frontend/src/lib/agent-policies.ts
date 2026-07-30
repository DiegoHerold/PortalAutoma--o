// Explica em pt-BR os campos de configuração de Agent que hoje só existiam como JSON cru
// (backend/modules/fleet/domain/configuration.py::AgentConfiguration + .../api/schemas.py::
// AgentConfigurationPatchRequest). Não inventa campos que o backend não tem.

export const AGENT_CONFIG_FIELD_HELP: Record<string, string> = {
  heartbeat_interval_seconds:
    "De quanto em quanto tempo o Agent deve enviar um heartbeat ao Portal. Quanto menor, mais rápido o Portal percebe quedas — mas mais tráfego.",
  stale_after_seconds:
    "Se o último heartbeat passou desse tempo, o Agent aparece como \"instável\" (stale) mesmo sem ter caído de vez. Deve ser maior que o intervalo de heartbeat.",
  offline_after_seconds:
    "Se o último heartbeat passou desse tempo, o Agent é considerado offline. Deve ser maior que o limite de \"instável\".",
  administrator_pool_limits:
    "Teto máximo de execuções simultâneas por tipo de pool (interactive/background/browser), definido pelo administrador — sobrepõe o que o próprio Agent recomenda.",
  enabled_pools: "Quais pools (interactive/background/browser) este Agent pode receber trabalho. Desmarcar um pool para de despachar esse tipo de tarefa para ele.",
  allowlist_capabilities: "Se preenchido, restringe o Agent a só aceitar automações que exigam exatamente essas capacidades (allowlist). Vazio = sem restrição.",
  restrictions: "Restrições adicionais livres (JSON), usadas por integrações/políticas específicas — não têm um formato fixo no backend.",
  desired_version: "Versão do Agent que o Portal vai pedir para ele atualizar (comando assíncrono, não é instantâneo).",
};

export const DEFAULT_AGENT_POOL_TYPES = ["interactive", "background", "browser"] as const;

export const AGENT_POOL_LABELS: Record<string, string> = {
  interactive: "Interativo",
  background: "Segundo plano",
  browser: "Navegador",
};

export function agentPoolLabel(poolType: string): string {
  return AGENT_POOL_LABELS[poolType] ?? poolType;
}
