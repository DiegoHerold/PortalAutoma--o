export type Worker = {
  id: number;
  name: string;
  hostname: string;
  ip_address?: string | null;
  agent_id?: string | null;
  machine_id?: string | null;
  agent_version?: string | null;
  os?: string | null;
  architecture?: string | null;
  capabilities_json?: unknown[] | null;
  last_payload_json?: Record<string, unknown> | null;
  status: string;
  connectivity_status?: string | null;
  administrative_status?: string | null;
  health_status?: string | null;
  occupancy_status?: string | null;
  desired_version?: string | null;
  cpu_percentage?: number | null;
  memory_percentage?: number | null;
  disk_free_mb?: number | null;
  interactive_session?: Record<string, unknown> | null;
  pools?: Record<string, unknown> | null;
  alerts?: string[] | null;
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
