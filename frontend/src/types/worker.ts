export type Worker = {
  id: number;
  name: string;
  hostname: string;
  ip_address?: string | null;
  status: string;
  max_concurrency: number;
  last_heartbeat_at?: string | null;
  is_active: boolean;
};
