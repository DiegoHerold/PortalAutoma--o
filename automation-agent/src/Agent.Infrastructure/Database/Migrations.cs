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
            """)
    };
}
