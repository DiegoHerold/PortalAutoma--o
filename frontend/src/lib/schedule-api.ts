import { apiRequest } from "@/lib/api";
import type {
  Schedule,
  ScheduleExecution,
  ScheduleWritePayload,
  SchedulePreviewPayload,
  SchedulePreviewResponse,
} from "@/types/schedule";

export function createSchedule(token: string, body: ScheduleWritePayload) {
  return apiRequest<Schedule>("/schedules", { method: "POST", token, body: JSON.stringify(body) });
}

export function updateSchedule(token: string, scheduleId: number, body: Partial<ScheduleWritePayload>) {
  return apiRequest<Schedule>(`/schedules/${scheduleId}`, { method: "PUT", token, body: JSON.stringify(body) });
}

function mutateStatus(token: string, scheduleId: number, action: "enable" | "pause" | "disable" | "archive") {
  return apiRequest<Schedule>(`/schedules/${scheduleId}/${action}`, { method: "POST", token });
}

export const enableSchedule = (token: string, scheduleId: number) => mutateStatus(token, scheduleId, "enable");
export const pauseSchedule = (token: string, scheduleId: number) => mutateStatus(token, scheduleId, "pause");
export const disableSchedule = (token: string, scheduleId: number) => mutateStatus(token, scheduleId, "disable");
export const archiveSchedule = (token: string, scheduleId: number) => mutateStatus(token, scheduleId, "archive");

export function triggerSchedule(token: string, scheduleId: number) {
  return apiRequest<ScheduleExecution>(`/schedules/${scheduleId}/trigger`, { method: "POST", token });
}

export function getScheduleHistory(token: string, scheduleId: number) {
  return apiRequest<ScheduleExecution[]>(`/schedules/${scheduleId}/history`, { token });
}

export function previewScheduleOccurrences(token: string, body: SchedulePreviewPayload) {
  return apiRequest<SchedulePreviewResponse>("/schedules/preview", { method: "POST", token, body: JSON.stringify(body) });
}
