export type StorageArtifact = {
  id: string;
  execution_id: string;
  task_execution_id: string;
  execution_attempt_id: string;
  name: string;
  content_type: string;
  status: string;
  stored_object_id: string | null;
  upload_session_id: string | null;
  size_bytes: number | null;
  sha256: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  uploaded_at: string | null;
  failed_at: string | null;
  failure_reason: string | null;
};
