namespace Biason.AutomationAgent.Infrastructure.Database;

public static class Migrations
{
    public static readonly IReadOnlyList<MigrationDefinition> All = new List<MigrationDefinition>
    {
        new(1, "initial_schema", """
            CREATE TABLE agent_identity (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                installation_id TEXT NOT NULL,
                agent_id TEXT,
                machine_id TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                registered_at_utc TEXT
            );

            CREATE TABLE agent_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_state TEXT NOT NULL,
                previous_state TEXT,
                last_transition_utc TEXT NOT NULL,
                reason TEXT,
                details TEXT
            );

            CREATE TABLE agent_state_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                reason TEXT,
                details TEXT,
                source TEXT,
                transitioned_at_utc TEXT NOT NULL
            );

            CREATE INDEX idx_agent_state_transitions_time ON agent_state_transitions(transitioned_at_utc DESC);

            CREATE TABLE machine_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at_utc TEXT NOT NULL,
                profile_json TEXT NOT NULL
            );

            CREATE INDEX idx_machine_profiles_time ON machine_profiles(captured_at_utc DESC);

            CREATE TABLE resource_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sampled_at_utc TEXT NOT NULL,
                cpu_usage_percent REAL NOT NULL,
                memory_total_mb INTEGER NOT NULL,
                memory_available_mb INTEGER NOT NULL,
                memory_used_mb INTEGER NOT NULL,
                memory_usage_percent REAL NOT NULL,
                disk_total_mb INTEGER NOT NULL,
                disk_free_mb INTEGER NOT NULL,
                disk_usage_percent REAL NOT NULL,
                agent_memory_mb INTEGER NOT NULL,
                process_count INTEGER NOT NULL,
                uptime_seconds INTEGER NOT NULL,
                database_size_kb INTEGER NOT NULL DEFAULT 0,
                logs_size_kb INTEGER NOT NULL DEFAULT 0,
                spool_size_kb INTEGER NOT NULL DEFAULT 0,
                cache_size_kb INTEGER NOT NULL DEFAULT 0,
                session_status TEXT
            );

            CREATE INDEX idx_resource_samples_time ON resource_samples(sampled_at_utc DESC);

            CREATE TABLE capabilities (
                key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                version TEXT,
                source TEXT,
                detected_at_utc TEXT NOT NULL,
                details_json TEXT
            );

            CREATE TABLE executions (
                execution_id TEXT PRIMARY KEY,
                current_state TEXT NOT NULL,
                previous_state TEXT,
                created_at_utc TEXT NOT NULL,
                last_transition_utc TEXT NOT NULL,
                automation_id TEXT,
                reason TEXT
            );

            CREATE TABLE execution_state_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                reason TEXT,
                details TEXT,
                source TEXT,
                transitioned_at_utc TEXT NOT NULL,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
            );

            CREATE INDEX idx_execution_transitions_id ON execution_state_transitions(execution_id, transitioned_at_utc DESC);

            CREATE TABLE outbox_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                sent_at_utc TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX idx_outbox_unsent ON outbox_events(sent_at_utc) WHERE sent_at_utc IS NULL;

            CREATE TABLE inbox_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                received_at_utc TEXT NOT NULL,
                processed_at_utc TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
            );

            CREATE INDEX idx_inbox_pending ON inbox_commands(status) WHERE status = 'pending';
            """),

        new(2, "execution_pipeline", """
            -- Expand executions table with Phase 2 columns
            ALTER TABLE executions ADD COLUMN automation_version_id TEXT;
            ALTER TABLE executions ADD COLUMN pool TEXT;
            ALTER TABLE executions ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE executions ADD COLUMN current_attempt_id TEXT;
            ALTER TABLE executions ADD COLUMN workspace_path TEXT;
            ALTER TABLE executions ADD COLUMN process_id INTEGER;
            ALTER TABLE executions ADD COLUMN reservation_id TEXT;
            ALTER TABLE executions ADD COLUMN timeout_seconds INTEGER;
            ALTER TABLE executions ADD COLUMN input_json TEXT;

            CREATE INDEX idx_executions_state ON executions(current_state);
            CREATE INDEX idx_executions_pool ON executions(pool) WHERE pool IS NOT NULL;

            -- Runtime artifacts (immutable store)
            CREATE TABLE runtime_artifacts (
                runtime_id TEXT NOT NULL,
                version TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'win-x64',
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                store_path TEXT NOT NULL,
                downloaded_at_utc TEXT NOT NULL,
                verified_at_utc TEXT,
                is_valid INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (runtime_id, version)
            );

            -- Package artifacts (immutable store)
            CREATE TABLE package_artifacts (
                package_id TEXT PRIMARY KEY,
                automation_id TEXT NOT NULL,
                automation_version_id TEXT NOT NULL,
                version TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                store_path TEXT NOT NULL,
                manifest_path TEXT NOT NULL,
                downloaded_at_utc TEXT NOT NULL,
                verified_at_utc TEXT,
                last_used_at_utc TEXT,
                is_valid INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX idx_package_artifacts_automation ON package_artifacts(automation_id, automation_version_id);
            CREATE INDEX idx_package_artifacts_lru ON package_artifacts(last_used_at_utc);

            -- Downloads tracking
            CREATE TABLE downloads (
                download_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                target_path TEXT NOT NULL,
                expected_sha256 TEXT NOT NULL,
                expected_size_bytes INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                bytes_downloaded INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at_utc TEXT NOT NULL,
                completed_at_utc TEXT,
                error_message TEXT
            );

            CREATE INDEX idx_downloads_status ON downloads(status);

            -- Execution attempts
            CREATE TABLE execution_attempts (
                attempt_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                current_state TEXT NOT NULL,
                pool TEXT NOT NULL,
                workspace_path TEXT,
                process_id INTEGER,
                runtime_id TEXT,
                package_id TEXT,
                created_at_utc TEXT NOT NULL,
                started_at_utc TEXT,
                completed_at_utc TEXT,
                exit_code INTEGER,
                error_message TEXT,
                peak_memory_mb INTEGER,
                cpu_time_seconds REAL,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
            );

            CREATE INDEX idx_execution_attempts_exec ON execution_attempts(execution_id);

            -- Execution events (streaming events from running executions)
            CREATE TABLE execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                data_json TEXT,
                occurred_at_utc TEXT NOT NULL,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id),
                FOREIGN KEY (attempt_id) REFERENCES execution_attempts(attempt_id)
            );

            CREATE INDEX idx_execution_events_exec ON execution_events(execution_id, occurred_at_utc);
            CREATE INDEX idx_execution_events_attempt ON execution_events(attempt_id, occurred_at_utc);

            -- Execution results
            CREATE TABLE execution_results (
                execution_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                success INTEGER NOT NULL,
                exit_code INTEGER,
                output_json TEXT,
                error_output TEXT,
                duration_ms INTEGER,
                peak_memory_mb INTEGER,
                cpu_time_seconds REAL,
                completed_at_utc TEXT NOT NULL,
                PRIMARY KEY (execution_id, attempt_id),
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id),
                FOREIGN KEY (attempt_id) REFERENCES execution_attempts(attempt_id)
            );

            -- Resource reservations
            CREATE TABLE resource_reservations (
                reservation_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                pool TEXT NOT NULL,
                slots INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                created_at_utc TEXT NOT NULL,
                expires_at_utc TEXT NOT NULL,
                released_at_utc TEXT,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
            );

            CREATE INDEX idx_reservations_status ON resource_reservations(status);
            CREATE INDEX idx_reservations_pool ON resource_reservations(pool, status);
            CREATE INDEX idx_reservations_expiry ON resource_reservations(expires_at_utc) WHERE status = 'active';

            -- Execution artifacts (output files from executions)
            CREATE TABLE execution_artifacts (
                artifact_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                local_path TEXT,
                storage_object_id TEXT,
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (execution_id) REFERENCES executions(execution_id),
                FOREIGN KEY (attempt_id) REFERENCES execution_attempts(attempt_id)
            );

            CREATE INDEX idx_execution_artifacts_exec ON execution_artifacts(execution_id);
            """)
    };
}
