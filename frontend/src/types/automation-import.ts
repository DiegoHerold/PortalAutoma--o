export type AutomationImportPreview = {
  staging_id: string | null;
  key: string;
  name: string;
  version: string;
  description?: string | null;
  category?: string | null;
  runtime_id: string;
  entrypoint_type: string;
  path?: string | null;
  manifest_path?: string | null;
  commit_sha?: string | null;
  source_type: "github" | "manual_upload";
  already_imported: boolean;
  validation_status: "valid" | "invalid";
  errors: string[];
  package_sha256: string;
  package_size: number;
};

export type AutomationVersion = {
  id: number;
  automation_id: number;
  version: string;
  status: "draft" | "validating" | "invalid" | "ready" | "published" | "deprecated" | "blocked" | "disabled";
  runtime_id: string;
  runtime_version?: string | null;
  entrypoint_type: string;
  application_type: string;
  artifact_bucket: string;
  artifact_object_key: string;
  artifact_size: number;
  artifact_sha256: string;
  source_commit_sha?: string | null;
  source_path?: string | null;
  created_at: string;
  published_at?: string | null;
};

export type AutomationSource = {
  id: number;
  automation_id: number;
  type: "github" | "manual_upload";
  owner?: string | null;
  repository?: string | null;
  branch?: string | null;
  automation_path?: string | null;
  manifest_path?: string | null;
  last_commit_sha?: string | null;
  last_synced_at?: string | null;
  sync_status?: string | null;
  original_filename?: string | null;
  uploaded_at?: string | null;
};

export type GithubIntegration = {
  id: number;
  installation_id: number;
  account_login: string;
  account_type: string;
  connected_at?: string | null;
  suspended_at?: string | null;
};

export type GithubRepository = {
  id: number;
  owner: string;
  name: string;
  full_name: string;
  default_branch: string;
  private: boolean;
};

export type GithubDiscoveryItem = {
  key: string | null;
  name: string | null;
  version: string | null;
  description?: string | null;
  category?: string | null;
  runtime_id?: string | null;
  entrypoint_type?: string | null;
  path: string;
  manifest_path: string;
  commit_sha: string;
  already_imported: boolean;
  validation_status: "valid" | "invalid";
  errors: string[];
};
