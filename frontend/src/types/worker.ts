export type Worker = {
  id: number;
  name: string;
  hostname: string;
  ip_address?: string | null;
  status: string;
  max_concurrency: number;
  last_heartbeat_at?: string | null;
  is_active: boolean;

  // Optional realtime fields
  active_jobs?: number | null;
};

export type WorkerPreference = {
  worker_id: number;
  worker_name?: string;
  priority_order: number;
  is_active?: boolean;
};
