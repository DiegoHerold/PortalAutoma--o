export type Trigger = {
  id: number;
  automation_id: number;
  trigger_type: string;
  route_path: string;
  secret_token: string;
  is_active: boolean;
};
