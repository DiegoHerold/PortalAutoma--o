using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionRepository : IExecutionRepository
{
    private readonly SqliteDatabaseManager _db;

    public ExecutionRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionRecord record, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO executions (execution_id, current_state, previous_state, created_at_utc, last_transition_utc, automation_id, reason)
            VALUES ($eid, $cs, $ps, $cat, $lt, $aid, $r);
            """;
        cmd.Parameters.AddWithValue("$eid", record.ExecutionId);
        cmd.Parameters.AddWithValue("$cs", record.CurrentState.ToString());
        cmd.Parameters.AddWithValue("$ps", record.PreviousState?.ToString() ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$cat", record.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$lt", record.LastTransitionUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$aid", (object?)record.AutomationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$r", (object?)record.Reason ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ExecutionRecord?> GetAsync(string executionId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT execution_id, current_state, previous_state, created_at_utc, last_transition_utc, automation_id, reason FROM executions WHERE execution_id = $eid;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct)) return null;
        return new ExecutionRecord
        {
            ExecutionId = reader.GetString(0),
            CurrentState = Enum.Parse<ExecutionState>(reader.GetString(1), ignoreCase: true),
            PreviousState = reader.IsDBNull(2) ? null : Enum.Parse<ExecutionState>(reader.GetString(2), ignoreCase: true),
            CreatedAtUtc = DateTime.Parse(reader.GetString(3)),
            LastTransitionUtc = DateTime.Parse(reader.GetString(4)),
            AutomationId = reader.IsDBNull(5) ? null : reader.GetString(5),
            Reason = reader.IsDBNull(6) ? null : reader.GetString(6)
        };
    }

    public async Task UpdateStateAsync(string executionId, ExecutionRecord record, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE executions SET current_state = $cs, previous_state = $ps, last_transition_utc = $lt, reason = $r
            WHERE execution_id = $eid;
            """;
        cmd.Parameters.AddWithValue("$cs", record.CurrentState.ToString());
        cmd.Parameters.AddWithValue("$ps", record.PreviousState?.ToString() ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$lt", record.LastTransitionUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$r", (object?)record.Reason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$eid", executionId);
        await cmd.ExecuteNonQueryAsync(ct);
    }
}
