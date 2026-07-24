export type TriggerCondition = "success" | "failed" | "always";

export type Trigger = {
  id: number;
  automation_id: number;
  trigger_type: string; // "https" | "chained"
  route_path: string;
  secret_token: string;
  is_active: boolean;
  parameter_mapping_json: Record<string, string> | null;
  template: string | null;
  source_automation_id: number | null;
  condition: TriggerCondition | null;
};

export type TriggerDryRunResult = {
  automation_id: number;
  parameters: Record<string, unknown>;
  valid: boolean;
  errors: string[];
};
