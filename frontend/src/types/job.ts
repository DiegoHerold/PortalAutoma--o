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
};
