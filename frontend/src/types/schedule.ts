export type RecurrenceType = "daily" | "weekly" | "monthly" | "once";

export type Schedule = {
  id: number;
  automation_id: number;
  cron_expression: string;
  timezone: string;
  is_active: boolean;
  recurrence_type: RecurrenceType;
  time_of_day: string; // "HH:MM"
  weekdays: number[] | null; // 0=Mon .. 6=Sun, set when recurrence_type === "weekly"
  day_of_month: number | null; // 1-31, or 0 = "último dia", set when recurrence_type === "monthly"
  specific_date: string | null; // "YYYY-MM-DD", set when recurrence_type === "once"
  is_one_time: boolean;
  last_dispatched_at: string | null;
};

export type ScheduleOccurrence = {
  schedule_id: number;
  automation_id: number;
  automation_name: string;
  category_id: number | null;
  recurrence_type: RecurrenceType;
  occurs_at: string;
  status: "upcoming" | "missed" | "queued" | "running" | "success" | "failed" | "cancelled";
  job_id: number | null;
};
