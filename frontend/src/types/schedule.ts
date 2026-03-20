export type Schedule = {
  id: number;
  automation_id: number;
  cron_expression: string;
  timezone: string;
  is_active: boolean;
};
