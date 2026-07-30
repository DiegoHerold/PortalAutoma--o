// Explica em pt-BR os campos de política de agendamento que hoje existem no backend
// (backend/modules/orchestration/scheduling/{api/schemas.py,application/use_cases.py})
// mas que antes só apareciam como JSON cru. Não inventa políticas que o backend não tem.

export type PolicyOption = { value: string; label: string; description: string };

export const MISFIRE_POLICY_OPTIONS: PolicyOption[] = [
  {
    value: "run_once_now",
    label: "Executar uma vez ao voltar",
    description:
      "Se o motor de agendamento ficou fora do ar e perdeu o horário previsto, dispara a execução perdida uma única vez assim que o sistema volta, em vez de simplesmente pular para a próxima ocorrência.",
  },
  {
    value: "skip",
    label: "Pular execuções perdidas",
    description:
      "Se o horário previsto passou além da janela de tolerância, a execução perdida é descartada (registrada como \"pulada\") e o agendamento só dispara novamente na próxima ocorrência normal.",
  },
];

export function misfirePolicyMeta(value?: string | null): PolicyOption {
  return MISFIRE_POLICY_OPTIONS.find((o) => o.value === value) ?? MISFIRE_POLICY_OPTIONS[0];
}

export const OVERLAP_POLICY_OPTIONS: PolicyOption[] = [
  {
    value: "forbid",
    label: "Proibir sobreposição",
    description:
      "Se a execução anterior deste agendamento ainda estiver rodando quando a próxima ocorrência vencer, a nova execução é pulada (registrada como \"pulada\") em vez de rodar em paralelo.",
  },
  {
    value: "allow",
    label: "Permitir sobreposição",
    description:
      "A próxima ocorrência dispara normalmente mesmo que a execução anterior deste agendamento ainda esteja rodando — podem existir duas ou mais execuções simultâneas do mesmo agendamento.",
  },
];

export function overlapPolicyMeta(value?: string | null): PolicyOption {
  return OVERLAP_POLICY_OPTIONS.find((o) => o.value === value) ?? OVERLAP_POLICY_OPTIONS[0];
}

/** Tolerância (em segundos) usada por _is_misfire: quanto tempo depois do horário previsto ainda conta como "no prazo". */
export function misfireGraceLabel(seconds?: number | null): string {
  const s = seconds ?? 0;
  if (s <= 0) return "sem tolerância — qualquer atraso conta como perdido";
  if (s < 60) return `${s} segundo(s) de tolerância`;
  if (s < 3600) return `${Math.round(s / 60)} minuto(s) de tolerância`;
  return `${Math.round((s / 3600) * 10) / 10} hora(s) de tolerância`;
}

export function maxCatchUpRunsLabel(count?: number | null): string {
  const n = count ?? 1;
  return n <= 1 ? "no máximo 1 execução de recuperação" : `no máximo ${n} execuções de recuperação em sequência`;
}
