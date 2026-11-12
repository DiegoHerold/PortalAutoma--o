import { expect, test } from "@playwright/test";

import { descrever, diaDaSemana, horaTexto, lado, mover, noFuso, noPasso } from "../src/lib/agenda";
import type { Schedule } from "../src/types/schedule";

/* Regras puras do calendário de Agendamentos (sem navegador). */

function agendamento(campos: Partial<Schedule>): Schedule {
  return { id: 1, automation_id: 7, automation_version_id: null, flow_id: null, flow_version_id: null, target_type: "automation",
    key: null, name: "Folha", cron_expression: null, timezone: "America/Sao_Paulo", is_active: true, recurrence_type: "daily",
    time_of_day: "08:00", weekdays: null, day_of_month: null, specific_date: null, is_one_time: false, last_dispatched_at: null,
    status: "active", schedule_type: "cron", interval_seconds: null, payload: null, misfire_policy: null, max_catch_up_runs: null,
    misfire_grace_seconds: null, overlap_policy: null, next_run_at: null, last_run_at: null, ...campos };
}

test("posição no fuso, dia da semana, hora e passo", () => {
  expect(noFuso("2026-11-12T13:30:00Z")).toEqual({ dia: "2026-11-12", minutos: 10 * 60 + 30 });  // UTC-3
  expect(noFuso("2026-11-13T02:15:00Z")).toEqual({ dia: "2026-11-12", minutos: 23 * 60 + 15 });  // ainda dia 12 em SP
  expect([diaDaSemana("2026-11-09"), diaDaSemana("2026-11-12"), diaDaSemana("2026-11-15")]).toEqual([0, 3, 6]);
  expect([horaTexto(0), horaTexto(9 * 60 + 5), horaTexto(1440)]).toEqual(["00:00", "09:05", "00:00"]);
  expect([noPasso(608), noPasso(-30), noPasso(1439)]).toEqual([615, 0, 1425]);
});

test("descrever a recorrência", () => {
  expect(descrever(agendamento({}))).toBe("Todo dia às 08:00");
  expect(descrever(agendamento({ recurrence_type: "weekly", weekdays: [2, 0] }))).toBe("Toda segunda e quarta às 08:00");
  expect(descrever(agendamento({ recurrence_type: "weekly", weekdays: [0, 1, 2, 3, 4] }))).toBe("De segunda a sexta às 08:00");
  expect(descrever(agendamento({ recurrence_type: "monthly", day_of_month: 10 }))).toBe("Dia 10 de cada mês às 08:00");
  expect(descrever(agendamento({ recurrence_type: "monthly", day_of_month: 0 }))).toBe("Último dia de cada mês às 08:00");
  expect(descrever(agendamento({ recurrence_type: "once", specific_date: "2026-11-20", time_of_day: "14:00" }))).toBe("Em 20/11/2026 às 14:00");
  expect(descrever(agendamento({ schedule_type: "interval", interval_seconds: 1800 }))).toBe("A cada 30 min");
  expect(descrever(agendamento({ schedule_type: "interval", interval_seconds: 7200 }))).toBe("A cada 2 h");
});

test("arrastar muda o agendamento conforme o tipo", () => {
  const unico = mover(agendamento({ recurrence_type: "once", specific_date: "2026-11-12" }), "2026-11-12", "2026-11-14", 10 * 60 + 30);
  expect(unico).toEqual({ ok: true, serie: false, antes: "Em 12/11/2026 às 08:00", depois: "Em 14/11/2026 às 10:30",
    patch: { recurrence_type: "once", time_of_day: "10:30", weekdays: null, day_of_month: null, specific_date: "2026-11-14", schedule_type: null } });
  const diario = mover(agendamento({}), "2026-11-12", "2026-11-13", 9 * 60);
  expect(diario.ok && diario.patch.time_of_day).toBe("09:00");
  expect(diario.ok && diario.serie).toBe(true);
  // segunda e quarta; arrasta a de quarta para sexta às 10:00
  const semanal = mover(agendamento({ recurrence_type: "weekly", weekdays: [0, 2] }), "2026-11-11", "2026-11-13", 600);
  expect(semanal).toMatchObject({ ok: true, depois: "Toda segunda e sexta às 10:00", patch: { weekdays: [0, 4] } });
  // arrastar para um dia que já está na lista junta os dois
  expect(mover(agendamento({ recurrence_type: "weekly", weekdays: [0, 2] }), "2026-11-11", "2026-11-09", 480))
    .toMatchObject({ ok: true, patch: { weekdays: [0] } });
  expect(mover(agendamento({ recurrence_type: "monthly", day_of_month: 10 }), "2026-11-10", "2026-11-25", 480))
    .toMatchObject({ ok: true, depois: "Dia 25 de cada mês às 08:00", patch: { day_of_month: 25 } });
  expect(mover(agendamento({ schedule_type: "interval", interval_seconds: 600 }), "2026-11-12", "2026-11-13", 0)).toMatchObject({ ok: false });
  expect(mover(agendamento({}), "2026-11-12", "2026-11-12", 480)).toEqual({ ok: false, motivo: "Nada mudou." });
});

test("o que se sobrepõe fica lado a lado", () => {
  const blocos = lado([
    { item: "a", inicio: 480, fim: 540 }, { item: "b", inicio: 500, fim: 560 }, { item: "c", inicio: 600, fim: 630 },
  ]);
  const por = Object.fromEntries(blocos.map((b) => [b.item as string, [b.coluna, b.colunas]]));
  expect(por).toEqual({ a: [0, 2], b: [1, 2], c: [0, 1] });
});
