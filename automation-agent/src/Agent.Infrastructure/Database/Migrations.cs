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
            """),

        new(3, "portal_integration", """
            -- =====================================================================
            -- Fase 3 — Integração com o Portal, telemetria resiliente e sessões.
            --
            -- Estritamente aditiva: nenhuma tabela das Fases 1 e 2 é recriada ou
            -- removida. outbox_events e inbox_commands ganham colunas via ALTER
            -- TABLE, preservando as colunas originais para compatibilidade.
            -- =====================================================================

            -- --- Registro do Agent no Portal ---
            CREATE TABLE agent_registration (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                agent_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                registered_at_utc TEXT NOT NULL,
                portal_api_base_url TEXT,
                portal_websocket_url TEXT,
                agent_version TEXT,
                last_confirmed_at_utc TEXT,
                revoked_at_utc TEXT,
                revocation_reason TEXT
            );

            -- Metadados da credencial. O segredo em si NUNCA é gravado aqui:
            -- fica no blob protegido (DPAPI) da tabela agent_credentials_protected.
            CREATE TABLE agent_credentials_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                credential_type TEXT NOT NULL,
                fingerprint TEXT,
                protection_mechanism TEXT NOT NULL,
                stored_at_utc TEXT NOT NULL,
                expires_at_utc TEXT,
                last_used_at_utc TEXT,
                revoked_at_utc TEXT,
                revocation_reason TEXT
            );

            -- Blob opaco produzido pelo ICredentialProtector.
            CREATE TABLE agent_credentials_protected (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                protected_blob BLOB NOT NULL,
                protection_mechanism TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            -- --- Conexão com o Portal ---
            CREATE TABLE portal_connections (
                connection_id TEXT PRIMARY KEY,
                agent_instance_id TEXT NOT NULL,
                state TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                connected_at_utc TEXT,
                disconnected_at_utc TEXT,
                last_message_at_utc TEXT,
                last_pong_at_utc TEXT,
                disconnect_reason TEXT,
                reconnect_attempt INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX idx_portal_connections_state ON portal_connections(state);

            CREATE TABLE connection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id TEXT,
                from_state TEXT,
                to_state TEXT NOT NULL,
                reason TEXT,
                detail TEXT,
                occurred_at_utc TEXT NOT NULL
            );

            CREATE INDEX idx_connection_events_time ON connection_events(occurred_at_utc DESC);

            -- --- Outbox: evolução aditiva ---
            ALTER TABLE outbox_events ADD COLUMN message_id TEXT;
            ALTER TABLE outbox_events ADD COLUMN message_type TEXT;
            ALTER TABLE outbox_events ADD COLUMN agent_id TEXT;
            ALTER TABLE outbox_events ADD COLUMN execution_id TEXT;
            ALTER TABLE outbox_events ADD COLUMN execution_attempt_id TEXT;
            ALTER TABLE outbox_events ADD COLUMN sequence INTEGER;
            ALTER TABLE outbox_events ADD COLUMN available_at_utc TEXT;
            ALTER TABLE outbox_events ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE outbox_events ADD COLUMN last_attempt_at_utc TEXT;
            ALTER TABLE outbox_events ADD COLUMN acknowledged_at_utc TEXT;
            ALTER TABLE outbox_events ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
            ALTER TABLE outbox_events ADD COLUMN payload_size_bytes INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE outbox_events ADD COLUMN last_error TEXT;

            -- Deduplicação por message_id. Índice parcial porque as linhas
            -- legadas (se houver) têm message_id nulo.
            CREATE UNIQUE INDEX idx_outbox_message_id
                ON outbox_events(message_id) WHERE message_id IS NOT NULL;

            -- Fila de envio: pendentes elegíveis, na ordem de criação.
            CREATE INDEX idx_outbox_dispatch
                ON outbox_events(status, available_at_utc, id)
                WHERE status IN ('pending', 'failed');

            CREATE INDEX idx_outbox_execution
                ON outbox_events(execution_attempt_id, sequence)
                WHERE execution_attempt_id IS NOT NULL;

            CREATE INDEX idx_outbox_unacked
                ON outbox_events(status) WHERE status = 'sent';

            -- --- Inbox: evolução aditiva ---
            ALTER TABLE inbox_commands ADD COLUMN message_id TEXT;
            ALTER TABLE inbox_commands ADD COLUMN correlation_id TEXT;
            ALTER TABLE inbox_commands ADD COLUMN execution_id TEXT;
            ALTER TABLE inbox_commands ADD COLUMN execution_attempt_id TEXT;
            ALTER TABLE inbox_commands ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE inbox_commands ADD COLUMN result TEXT;
            ALTER TABLE inbox_commands ADD COLUMN error TEXT;

            -- Chave da idempotência: um comando repetido não pode rodar duas vezes.
            CREATE UNIQUE INDEX idx_inbox_message_id
                ON inbox_commands(message_id) WHERE message_id IS NOT NULL;

            CREATE INDEX idx_inbox_status_time ON inbox_commands(status, received_at_utc);

            CREATE TABLE message_acknowledgements (
                message_id TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                acknowledged_at_utc TEXT NOT NULL,
                detail TEXT
            );

            CREATE INDEX idx_message_ack_time ON message_acknowledgements(acknowledged_at_utc DESC);

            -- --- Oferta, commit e lease ---
            CREATE TABLE execution_offers (
                offer_message_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                automation_id TEXT NOT NULL,
                automation_version TEXT,
                runtime_id TEXT,
                runtime_version TEXT,
                mode TEXT NOT NULL,
                pool TEXT NOT NULL,
                offer_payload_json TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason_code TEXT,
                reason_message TEXT,
                reservation_id TEXT,
                received_at_utc TEXT NOT NULL,
                decided_at_utc TEXT,
                reservation_expires_at_utc TEXT
            );

            CREATE INDEX idx_execution_offers_exec ON execution_offers(execution_id);
            CREATE INDEX idx_execution_offers_decision ON execution_offers(decision);
            CREATE INDEX idx_execution_offers_expiry
                ON execution_offers(reservation_expires_at_utc)
                WHERE decision = 'accepted';

            CREATE TABLE execution_commits (
                commit_message_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                reservation_id TEXT,
                accepted INTEGER NOT NULL,
                rejection_reason TEXT,
                received_at_utc TEXT NOT NULL,
                processed_at_utc TEXT
            );

            -- Um commit por tentativa: barra duplicação de execução.
            CREATE UNIQUE INDEX idx_execution_commits_attempt
                ON execution_commits(execution_attempt_id) WHERE accepted = 1;

            CREATE INDEX idx_execution_commits_exec ON execution_commits(execution_id);

            CREATE TABLE execution_leases (
                lease_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                state TEXT NOT NULL,
                granted_at_utc TEXT NOT NULL,
                expires_at_utc TEXT NOT NULL,
                last_renewed_at_utc TEXT,
                renew_attempt_count INTEGER NOT NULL DEFAULT 0,
                lost_at_utc TEXT,
                lost_reason TEXT
            );

            CREATE INDEX idx_execution_leases_attempt ON execution_leases(execution_attempt_id);
            CREATE INDEX idx_execution_leases_active
                ON execution_leases(expires_at_utc) WHERE state = 'active';

            -- --- Sessões e Session Runner ---
            CREATE TABLE session_runners (
                session_runner_instance_id TEXT PRIMARY KEY,
                session_id INTEGER NOT NULL,
                user_name TEXT,
                session_type TEXT,
                process_id INTEGER,
                version TEXT,
                desktop_state TEXT,
                capabilities_json TEXT,
                state TEXT NOT NULL,
                registered_at_utc TEXT NOT NULL,
                last_heartbeat_at_utc TEXT,
                disconnected_at_utc TEXT,
                session_token_fingerprint TEXT,
                session_token_expires_at_utc TEXT
            );

            CREATE INDEX idx_session_runners_session ON session_runners(session_id);
            CREATE INDEX idx_session_runners_state ON session_runners(state);

            CREATE TABLE interactive_sessions (
                session_id INTEGER PRIMARY KEY,
                user_name TEXT,
                domain_name TEXT,
                station_name TEXT,
                session_type TEXT,
                status TEXT NOT NULL,
                is_locked INTEGER,
                screen_width INTEGER,
                screen_height INTEGER,
                monitor_count INTEGER,
                dpi_scale REAL,
                session_runner_instance_id TEXT,
                observed_at_utc TEXT NOT NULL
            );

            CREATE TABLE session_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                session_runner_instance_id TEXT,
                event_type TEXT NOT NULL,
                detail_json TEXT,
                occurred_at_utc TEXT NOT NULL
            );

            CREATE INDEX idx_session_events_time ON session_events(occurred_at_utc DESC);
            CREATE INDEX idx_session_events_session ON session_events(session_id, occurred_at_utc DESC);

            -- --- Locks de recurso exclusivo do desktop ---
            -- Persistidos pelo Agent Service: não podem depender da memória
            -- do Session Runner (seção 28).
            CREATE TABLE resource_locks (
                resource_key TEXT PRIMARY KEY,
                owner_execution_id TEXT NOT NULL,
                owner_execution_attempt_id TEXT NOT NULL,
                session_id INTEGER,
                acquired_at_utc TEXT NOT NULL,
                lease_expires_at_utc TEXT NOT NULL,
                last_renewed_at_utc TEXT,
                released_at_utc TEXT
            );

            CREATE INDEX idx_resource_locks_owner ON resource_locks(owner_execution_attempt_id);
            CREATE INDEX idx_resource_locks_expiry ON resource_locks(lease_expires_at_utc);

            -- --- Artefatos pendentes de upload ---
            CREATE TABLE pending_artifacts (
                artifact_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                local_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                kind TEXT,
                created_at_utc TEXT NOT NULL,
                available_at_utc TEXT,
                uploaded_at_utc TEXT,
                confirmed_at_utc TEXT,
                remote_object_id TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT
            );

            CREATE INDEX idx_pending_artifacts_status ON pending_artifacts(status, available_at_utc);
            CREATE INDEX idx_pending_artifacts_exec ON pending_artifacts(execution_id);

            CREATE TABLE artifact_upload_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                started_at_utc TEXT NOT NULL,
                completed_at_utc TEXT,
                bytes_sent INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                http_status INTEGER,
                error_message TEXT,
                FOREIGN KEY (artifact_id) REFERENCES pending_artifacts(artifact_id)
            );

            CREATE INDEX idx_artifact_attempts_artifact ON artifact_upload_attempts(artifact_id);

            -- --- Erros de protocolo e sincronização ---
            CREATE TABLE protocol_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                message_type TEXT,
                error_code TEXT NOT NULL,
                error_message TEXT,
                direction TEXT NOT NULL,
                occurred_at_utc TEXT NOT NULL
            );

            CREATE INDEX idx_protocol_errors_time ON protocol_errors(occurred_at_utc DESC);

            CREATE TABLE sync_runs (
                sync_id TEXT PRIMARY KEY,
                connection_id TEXT,
                started_at_utc TEXT NOT NULL,
                completed_at_utc TEXT,
                running_executions_reported INTEGER NOT NULL DEFAULT 0,
                leases_reported INTEGER NOT NULL DEFAULT 0,
                outbox_pending_reported INTEGER NOT NULL DEFAULT 0,
                reconciled_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            );

            CREATE INDEX idx_sync_runs_time ON sync_runs(started_at_utc DESC);

            -- --- Execuções: vínculo com o Portal ---
            ALTER TABLE executions ADD COLUMN mode TEXT;
            ALTER TABLE executions ADD COLUMN session_id INTEGER;
            ALTER TABLE executions ADD COLUMN lease_id TEXT;
            ALTER TABLE executions ADD COLUMN origin TEXT NOT NULL DEFAULT 'local';
            ALTER TABLE executions ADD COLUMN offer_message_id TEXT;
            """),

        new(4, "session_runner_connections", """
            CREATE TABLE session_runner_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_runner_instance_id TEXT NOT NULL,
                session_id INTEGER NOT NULL,
                connected_at_utc TEXT NOT NULL,
                authenticated_at_utc TEXT,
                disconnected_at_utc TEXT,
                disconnect_reason TEXT,
                remote_process_id INTEGER,
                protocol_version TEXT,
                status TEXT NOT NULL
            );

            CREATE INDEX idx_session_runner_connections_runner
                ON session_runner_connections(session_runner_instance_id, connected_at_utc DESC);

            CREATE INDEX idx_session_runner_connections_time
                ON session_runner_connections(connected_at_utc DESC);
            """),

        new(5, "interactive_pool_execution", """
            -- Fase 2 / Bloco 5: pool interativo, locks, processos e artifacts de screenshot.
            -- Evolucao aditiva da tabela resource_locks criada no Bloco 4.
            ALTER TABLE resource_locks ADD COLUMN status TEXT NOT NULL DEFAULT 'Reserved';

            CREATE INDEX idx_resource_locks_status
                ON resource_locks(status, lease_expires_at_utc);

            CREATE TABLE interactive_execution_assignments (
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                session_id INTEGER NOT NULL,
                session_runner_instance_id TEXT NOT NULL,
                reservation_id TEXT,
                workspace_path TEXT,
                runtime_path TEXT,
                package_path TEXT,
                status TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                started_at_utc TEXT,
                completed_at_utc TEXT,
                last_heartbeat_at_utc TEXT,
                cancellation_requested_at_utc TEXT,
                execution_host_process_id INTEGER,
                exit_code INTEGER,
                error_code TEXT,
                error_message TEXT,
                PRIMARY KEY (execution_id, execution_attempt_id)
            );

            CREATE INDEX idx_interactive_assignments_status
                ON interactive_execution_assignments(status, session_id);

            CREATE INDEX idx_interactive_assignments_runner
                ON interactive_execution_assignments(session_runner_instance_id, status);

            CREATE TABLE interactive_execution_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                process_id INTEGER NOT NULL,
                parent_process_id INTEGER,
                session_id INTEGER,
                process_path TEXT,
                process_owner TEXT,
                started_at_utc TEXT,
                observed_at_utc TEXT NOT NULL,
                exited_at_utc TEXT,
                exit_code INTEGER,
                kind TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE INDEX idx_interactive_processes_attempt
                ON interactive_execution_processes(execution_id, execution_attempt_id);

            CREATE INDEX idx_interactive_processes_pid
                ON interactive_execution_processes(process_id, session_id);

            CREATE TABLE interactive_execution_screenshots (
                artifact_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                session_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                local_path TEXT NOT NULL,
                captured_at_utc TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                sha256 TEXT,
                size_bytes INTEGER NOT NULL
            );

            CREATE INDEX idx_interactive_screenshots_attempt
                ON interactive_execution_screenshots(execution_id, execution_attempt_id);

            CREATE TABLE application_process_ownership (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                execution_attempt_id TEXT NOT NULL,
                application_key TEXT NOT NULL,
                process_id INTEGER NOT NULL,
                session_id INTEGER,
                process_path TEXT,
                window_title TEXT,
                started_at_utc TEXT,
                observed_at_utc TEXT NOT NULL,
                ownership_kind TEXT NOT NULL,
                policy TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE INDEX idx_app_process_ownership_attempt
                ON application_process_ownership(execution_id, execution_attempt_id);

            CREATE INDEX idx_app_process_ownership_app
                ON application_process_ownership(application_key, session_id, status);
            """)
    };
}
