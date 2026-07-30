export type TriggerCondition = "success" | "failed" | "always";

export type Trigger = {
  id: number;
  name: string | null;
  automation_id: number;
  trigger_type: string;
  route_path: string;
  is_active: boolean;
  parameter_mapping_json: Record<string, string> | null;
  template: string | null;
  source_automation_id: number | null;
  condition: TriggerCondition | null;
  secret_configured: boolean;
  secret_last_four: string | null;
  secret_created_at: string | null;
  secret_rotated_at: string | null;
  method: "POST" | string;
  required_header: string;
  invocation_url: string | null;
  created_at: string | null;
  updated_at: string | null;
  last_invoked_at: string | null;
  last_execution_id: string | null;
  last_execution_status: string | null;
  last_execution_duration_seconds: number | null;
};

export type TriggerConfig = {
  backend_public_url: string;
  invoke_base_url: string;
  method: string;
  required_header: string;
};

export type TriggerCreateResult = Trigger & {
  secret_token: string | null;
};

export type TriggerRotateSecretResult = {
  secret_token: string;
  created_at: string;
  previous_secret_revoked: boolean;
  secret_last_four: string;
};

export type TriggerDryRunResult = {
  automation_id: number;
  parameters: Record<string, unknown>;
  valid: boolean;
  errors: string[];
};
