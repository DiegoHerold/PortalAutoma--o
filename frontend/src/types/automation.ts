export type Automation = {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  category_id: number;
  executor_type: string;
  package_url?: string | null;
  package_sha256?: string | null;
  default_priority: string;
  timeout_seconds: number;
  max_retries: number;
  is_active: boolean;
};
