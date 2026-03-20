export type Execution = {
  id: number;
  job_id: number;
  worker_id: number | null;
  execution_status: string;
  started_at: string | null;
  finished_at: string | null;
  result_summary: string | null;
  result_payload_json?: Record<string, unknown> | null;
  logs?: Array<{
    id: number;
    level: string;
    message: string;
    created_at: string;
  }>;
};
