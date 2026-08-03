using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Persistence;

/// <summary>
/// Cobertura das migrations 1 a 5.
///
/// Usa <see cref="TestHelper"/> em vez de construir o SqliteDatabaseManager
/// diretamente: ele exige IDirectoryResolver e IOptions&lt;DatabaseOptions&gt;,
/// e o helper já monta esse conjunto sobre um diretório temporário isolado.
/// </summary>
public sealed class MigrationTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync() => await _helper.InitializeDatabaseAsync();

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    private async Task<List<string>> GetTablesAsync()
    {
        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;";

        var tables = new List<string>();
        using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            tables.Add(reader.GetString(0));
        return tables;
    }

    private async Task<List<string>> GetColumnsAsync(string table)
    {
        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"PRAGMA table_info({table});";

        var columns = new List<string>();
        using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            columns.Add(reader.GetString(1));
        return columns;
    }

    [Fact]
    public async Task Phase1And2Tables_StillExist()
    {
        var tables = await GetTablesAsync();

        tables.Should().Contain("agent_identity");
        tables.Should().Contain("agent_state");
        tables.Should().Contain("machine_profiles");
        tables.Should().Contain("resource_samples");
        tables.Should().Contain("capabilities");
        tables.Should().Contain("executions");
        tables.Should().Contain("runtime_artifacts");
        tables.Should().Contain("package_artifacts");
        tables.Should().Contain("execution_attempts");
        tables.Should().Contain("execution_events");
        tables.Should().Contain("resource_reservations");
        tables.Should().Contain("outbox_events");
        tables.Should().Contain("inbox_commands");
    }

    [Fact]
    public async Task Migration3_CreatesPortalTables()
    {
        var tables = await GetTablesAsync();

        tables.Should().Contain("agent_registration");
        tables.Should().Contain("agent_credentials_metadata");
        tables.Should().Contain("agent_credentials_protected");
        tables.Should().Contain("portal_connections");
        tables.Should().Contain("connection_events");
        tables.Should().Contain("message_acknowledgements");
        tables.Should().Contain("execution_offers");
        tables.Should().Contain("execution_commits");
        tables.Should().Contain("execution_leases");
        tables.Should().Contain("session_runners");
        tables.Should().Contain("interactive_sessions");
        tables.Should().Contain("session_events");
        tables.Should().Contain("session_runner_connections");
        tables.Should().Contain("resource_locks");
        tables.Should().Contain("interactive_execution_assignments");
        tables.Should().Contain("interactive_execution_processes");
        tables.Should().Contain("interactive_execution_screenshots");
        tables.Should().Contain("application_process_ownership");
        tables.Should().Contain("pending_artifacts");
        tables.Should().Contain("artifact_upload_attempts");
        tables.Should().Contain("protocol_errors");
        tables.Should().Contain("sync_runs");
    }

    [Fact]
    public async Task Migration3_ExtendsOutboxAdditively()
    {
        var columns = await GetColumnsAsync("outbox_events");

        // Colunas originais preservadas
        columns.Should().Contain("event_type");
        columns.Should().Contain("payload_json");
        columns.Should().Contain("created_at_utc");
        columns.Should().Contain("retry_count");

        // Colunas da Fase 3
        columns.Should().Contain("message_id");
        columns.Should().Contain("message_type");
        columns.Should().Contain("execution_attempt_id");
        columns.Should().Contain("sequence");
        columns.Should().Contain("available_at_utc");
        columns.Should().Contain("attempt_count");
        columns.Should().Contain("acknowledged_at_utc");
        columns.Should().Contain("status");
    }

    [Fact]
    public async Task Migration3_ExtendsInboxAdditively()
    {
        var columns = await GetColumnsAsync("inbox_commands");

        columns.Should().Contain("command_type");
        columns.Should().Contain("payload_json");
        columns.Should().Contain("received_at_utc");

        columns.Should().Contain("message_id");
        columns.Should().Contain("correlation_id");
        columns.Should().Contain("result");
        columns.Should().Contain("error");
    }

    [Fact]
    public async Task Migration3_AddsPortalColumnsToExecutions()
    {
        var columns = await GetColumnsAsync("executions");

        columns.Should().Contain("mode");
        columns.Should().Contain("session_id");
        columns.Should().Contain("lease_id");
        columns.Should().Contain("origin");
        columns.Should().Contain("offer_message_id");
    }

    [Fact]
    public async Task Migration5_ExtendsResourceLocksAndCreatesInteractiveTables()
    {
        var lockColumns = await GetColumnsAsync("resource_locks");
        lockColumns.Should().Contain("resource_key");
        lockColumns.Should().Contain("owner_execution_id");
        lockColumns.Should().Contain("owner_execution_attempt_id");
        lockColumns.Should().Contain("session_id");
        lockColumns.Should().Contain("lease_expires_at_utc");
        lockColumns.Should().Contain("last_renewed_at_utc");
        lockColumns.Should().Contain("status");

        (await GetColumnsAsync("interactive_execution_assignments")).Should().Contain(new[]
        {
            "execution_id",
            "execution_attempt_id",
            "session_id",
            "session_runner_instance_id",
            "status",
            "execution_host_process_id"
        });

        (await GetColumnsAsync("interactive_execution_processes")).Should().Contain(new[]
        {
            "process_id",
            "session_id",
            "process_path",
            "kind",
            "status"
        });

        (await GetColumnsAsync("interactive_execution_screenshots")).Should().Contain(new[]
        {
            "artifact_id",
            "reason",
            "local_path",
            "sha256",
            "size_bytes"
        });

        (await GetColumnsAsync("application_process_ownership")).Should().Contain(new[]
        {
            "application_key",
            "process_id",
            "policy",
            "ownership_kind",
            "status"
        });
    }

    // inbox-deduplication (nível de esquema): o índice único é a garantia final
    // de que um message_id repetido não vira duas linhas.
    [Fact]
    public async Task InboxMessageId_IsUnique()
    {
        using var conn = _helper.DbManager.CreateConnection();

        async Task InsertAsync(string messageId)
        {
            using var cmd = conn.CreateCommand();
            cmd.CommandText = """
                INSERT INTO inbox_commands (command_type, payload_json, received_at_utc, status, message_id)
                VALUES ('execution.offer', '{}', '2026-07-31T12:00:00Z', 'received', $mid);
                """;
            cmd.Parameters.AddWithValue("$mid", messageId);
            await cmd.ExecuteNonQueryAsync();
        }

        await InsertAsync("msg_dup");

        var act = async () => await InsertAsync("msg_dup");
        await act.Should().ThrowAsync<Microsoft.Data.Sqlite.SqliteException>();
    }

    [Fact]
    public async Task OutboxMessageId_IsUnique()
    {
        using var conn = _helper.DbManager.CreateConnection();

        async Task InsertAsync(string messageId)
        {
            using var cmd = conn.CreateCommand();
            cmd.CommandText = """
                INSERT INTO outbox_events (event_type, payload_json, created_at_utc, message_id, message_type, status)
                VALUES ('execution.log', '{}', '2026-07-31T12:00:00Z', $mid, 'execution.log', 'pending');
                """;
            cmd.Parameters.AddWithValue("$mid", messageId);
            await cmd.ExecuteNonQueryAsync();
        }

        await InsertAsync("msg_out_dup");

        var act = async () => await InsertAsync("msg_out_dup");
        await act.Should().ThrowAsync<Microsoft.Data.Sqlite.SqliteException>();
    }

    // Um único commit aceito por tentativa: base do duplicated-commit.
    [Fact]
    public async Task AcceptedCommit_IsUniquePerAttempt()
    {
        using var conn = _helper.DbManager.CreateConnection();

        async Task InsertAsync(string commitMessageId)
        {
            using var cmd = conn.CreateCommand();
            cmd.CommandText = """
                INSERT INTO execution_commits
                    (commit_message_id, execution_id, execution_attempt_id, accepted, received_at_utc)
                VALUES ($cmid, 'exec_1', 'att_1', 1, '2026-07-31T12:00:00Z');
                """;
            cmd.Parameters.AddWithValue("$cmid", commitMessageId);
            await cmd.ExecuteNonQueryAsync();
        }

        await InsertAsync("msg_commit_1");

        // Mesmo com message_id diferente, a mesma tentativa não pode ser confirmada duas vezes.
        var act = async () => await InsertAsync("msg_commit_2");
        await act.Should().ThrowAsync<Microsoft.Data.Sqlite.SqliteException>();
    }

    [Fact]
    public async Task AllMigrations_AreRecorded()
    {
        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT version FROM schema_migrations ORDER BY version;";

        var versions = new List<int>();
        using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            versions.Add(reader.GetInt32(0));

        versions.Should().Equal(1, 2, 3, 4, 5);
    }

    [Fact]
    public async Task Initialize_IsIdempotent()
    {
        // Segunda inicialização sobre o mesmo banco não deve reaplicar migrations.
        await _helper.DbManager.InitializeAsync();

        (await _helper.DbManager.VerifyIntegrityAsync()).Should().BeTrue();

        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM schema_migrations;";
        Convert.ToInt64(await cmd.ExecuteScalarAsync()).Should().Be(5);
    }
}
