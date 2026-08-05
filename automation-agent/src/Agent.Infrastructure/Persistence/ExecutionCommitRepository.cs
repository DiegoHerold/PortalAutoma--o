using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionCommitRepository : IExecutionCommitRepository
{
    private readonly SqliteDatabaseManager _db;
    public ExecutionCommitRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionCommitRecord commit, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO execution_commits (
                commit_message_id, execution_id, execution_attempt_id, reservation_id,
                accepted, rejection_reason, received_at_utc, processed_at_utc
            ) VALUES ($id, $eid, $aid, $resid, $acc, $reason, $recv, $proc);
            """;
        cmd.Parameters.AddWithValue("$id", commit.CommitMessageId);
        cmd.Parameters.AddWithValue("$eid", commit.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", commit.ExecutionAttemptId);
        cmd.Parameters.AddWithValue("$resid", (object?)commit.ReservationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$acc", commit.Accepted ? 1 : 0);
        cmd.Parameters.AddWithValue("$reason", (object?)commit.RejectionReason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$recv", commit.ReceivedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$proc", commit.ProcessedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ExecutionCommitRecord?> GetAcceptedByAttemptAsync(string executionAttemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_commits WHERE execution_attempt_id = $aid AND accepted = 1 LIMIT 1;";
        cmd.Parameters.AddWithValue("$aid", executionAttemptId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    private static ExecutionCommitRecord Map(SqliteDataReader r) => new()
    {
        CommitMessageId = r.GetString(r.GetOrdinal("commit_message_id")),
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        ExecutionAttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
        ReservationId = r.IsDBNull(r.GetOrdinal("reservation_id")) ? null : r.GetString(r.GetOrdinal("reservation_id")),
        Accepted = r.GetInt32(r.GetOrdinal("accepted")) == 1,
        RejectionReason = r.IsDBNull(r.GetOrdinal("rejection_reason")) ? null : r.GetString(r.GetOrdinal("rejection_reason")),
        ReceivedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("received_at_utc"))),
        ProcessedAtUtc = r.IsDBNull(r.GetOrdinal("processed_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("processed_at_utc")))
    };
}
