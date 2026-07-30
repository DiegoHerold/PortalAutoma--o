export type RuntimeVersionStatus = "draft" | "validating" | "published" | "deprecated" | "blocked";

export type AutomationVersionStatus =
  | "draft"
  | "validating"
  | "ready"
  | "invalid"
  | "published"
  | "deprecated"
  | "blocked";

export type RuntimeCreateRequest = {
  key: string;
  name: string;
  description?: string | null;
};

export type RuntimeVersionCreateRequest = {
  version: string;
  operating_system?: string;
  architecture?: string;
  minimum_agent_version?: string | null;
  supported_entrypoints: string[];
  supported_execution_modes: string[];
  metadata: Record<string, unknown>;
};

export type RuntimeVersionResponse = {
  id: string;
  runtime_id: string;
  version: string;
  operating_system: string;
  architecture: string;
  status: RuntimeVersionStatus;
  minimum_agent_version?: string | null;
  supported_entrypoints: string[];
  supported_execution_modes: string[];
  metadata: Record<string, unknown>;
  created_at?: string | null;
  published_at?: string | null;
  deprecated_at?: string | null;
  blocked_at?: string | null;
};

export type RuntimeResponse = RuntimeCreateRequest & {
  id: string;
  status: "active" | "disabled" | "archived" | string;
  versions?: RuntimeVersionResponse[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type AutomationVersionCreateRequest = {
  raw_manifest: string;
  release_notes?: string | null;
  source_repository?: string | null;
  source_branch?: string | null;
  source_tag?: string | null;
  source_commit_sha?: string | null;
  build_id?: string | null;
};

export type AutomationVersionResponse = {
  id: number;
  automation_id: number;
  version: string;
  status: AutomationVersionStatus;
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
  manifest_id?: string | null;
  package_id?: string | null;
  runtime_version_id?: string | null;
  validation_errors?: Array<Record<string, unknown>> | null;
};

export type PackageUploadCreateRequest = {
  file_name: string;
  expected_size_bytes?: number | null;
  expected_sha256?: string | null;
};

export type PackageUploadResponse = {
  id: string;
  stored_object_id: string;
  package_id: string;
  upload_url?: string | null;
  expires_at?: string | null;
};

export type PackageResponse = {
  id: string;
  automation_version_id: number;
  stored_object_id: string;
  package_format: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  status: string;
  validation_result?: PackageValidationResponse | null;
};

export type PackageValidationIssue = {
  code?: string;
  path?: string;
  message?: string;
  details?: Record<string, unknown>;
  [key: string]: unknown;
};

export type PackageValidationResponse = {
  valid?: boolean;
  issues?: PackageValidationIssue[];
  [key: string]: unknown;
};

export type BlockRequest = {
  reason?: string | null;
};

