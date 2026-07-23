export type Job = {
  id: number;
  automation_id: number;
  requested_by_user_id: number | null;
  status: string;
  priority: string;
  payload_json: Record<string, unknown> | null;
  scheduled_for: string | null;
  assigned_worker_id: number | null;
  error_message: string | null;

  // Optional fields populated by the realtime/ETA backend (degrade gracefully if absent)
  automation_name?: string | null;
  worker_name?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  estimated_start?: string | null;
  estimated_end?: string | null;
  estimated_duration_seconds?: number | null;
  queue_position?: number | null;
  created_at?: string | null;
};
