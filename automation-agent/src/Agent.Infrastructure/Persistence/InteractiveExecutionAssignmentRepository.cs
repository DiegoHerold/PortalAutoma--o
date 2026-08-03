using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class InteractiveExecutionAssignmentRepository : IInteractiveExecutionAssignmentRepository
{
    private static readonly string ActiveStatuses = "'Reserved','Preparing','Starting','Running','CancelRequested','Cancelling'";
    private readonly SqliteDatabaseManager _db;

    public InteractiveExecutionAssignmentRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(InteractiveExecutionAssignment assignment, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO interactive_execution_assignments (
                execution_id, execution_attempt_id, session_id, session_runner_instance_id, reservation_id,
                workspace_path, runtime_path, package_path, status, created_at_utc, started_at_utc,
                completed_at_utc, last_heartbeat_at_utc, cancellation_requested_at_utc,
                execution_host_process_id, exit_code, error_code, error_message)
            VALUES ($eid, $aid, $sid, $runner, $rid, $workspace, $runtime, $package, $status, $created,
                $started, $completed, $heartbeat, $cancel, $pid, $exit, $ecode, $emsg)
            ON CONFLICT(execution_id, execution_attempt_id) DO UPDATE SET
                session_id = excluded.session_id,
                session_runner_instance_id = excluded.session_runner_instance_id,
                reservation_id = excluded.reservation_id,
                workspace_path = excluded.workspace_path,
                runtime_path = excluded.runtime_path,
                package_path = excluded.package_path,
                status = excluded.status,
                error_code = excluded.error_code,
                error_message = excluded.error_message;
            """;
        Bind(cmd, assignment);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<InteractiveExecutionAssignment?> GetAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_execution_assignments WHERE execution_id = $eid AND execution_attempt_id = $aid;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? Map(reader) : null;
    }

    public async Task<IReadOnlyList<InteractiveExecutionAssignment>> GetActiveAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"SELECT * FROM interactive_execution_assignments WHERE status IN ({ActiveStatuses}) ORDER BY created_at_utc;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<InteractiveExecutionAssignment>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_execution_assignments ORDER BY created_at_utc DESC;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task<int> CountActiveAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"SELECT COUNT(*) FROM interactive_execution_assignments WHERE status IN ({ActiveStatuses});";
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task<int> CountActiveBySessionAsync(int sessionId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"SELECT COUNT(*) FROM interactive_execution_assignments WHERE session_id = $sid AND status IN ({ActiveStatuses});";
        cmd.Parameters.AddWithValue("$sid", sessionId);
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task UpdateStatusAsync(string executionId, string attemptId, InteractiveExecutionStatus status, DateTime nowUtc, string? errorCode = null, string? errorMessage = null, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE interactive_execution_assignments
            SET status = $status,
                completed_at_utc = CASE WHEN $terminal = 1 THEN COALESCE(completed_at_utc, $now) ELSE completed_at_utc END,
                cancellation_requested_at_utc = CASE WHEN $cancel = 1 THEN COALESCE(cancellation_requested_at_utc, $now) ELSE cancellation_requested_at_utc END,
                error_code = COALESCE($ecode, error_code),
                error_message = COALESCE($emsg, error_message)
            WHERE execution_id = $eid AND execution_attempt_id = $aid;
            """;
        cmd.Parameters.AddWithValue("$status", status.ToString());
        cmd.Parameters.AddWithValue("$terminal", IsTerminal(status) ? 1 : 0);
        cmd.Parameters.AddWithValue("$cancel", status == InteractiveExecutionStatus.CancelRequested ? 1 : 0);
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$ecode", (object?)errorCode ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$emsg", (object?)errorMessage ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkStartedAsync(string executionId, string attemptId, int processId, DateTime nowUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE interactive_execution_assignments
            SET status = 'Running',
                started_at_utc = COALESCE(started_at_utc, $now),
                last_heartbeat_at_utc = $now,
                execution_host_process_id = $pid
            WHERE execution_id = $eid AND execution_attempt_id = $aid;
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$pid", processId);
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkCompletedAsync(string executionId, string attemptId, InteractiveExecutionStatus status, int? exitCode, DateTime nowUtc, string? errorCode, string? errorMessage, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE interactive_execution_assignments
            SET status = $status,
                completed_at_utc = COALESCE(completed_at_utc, $now),
                exit_code = $exit,
                error_code = $ecode,
                error_message = $emsg
            WHERE execution_id = $eid AND execution_attempt_id = $aid;
            """;
        cmd.Parameters.AddWithValue("$status", status.ToString());
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$exit", exitCode.HasValue ? exitCode.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$ecode", (object?)errorCode ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$emsg", (object?)errorMessage ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task UpdatePreparedPathsAsync(string executionId, string attemptId, string workspacePath, string runtimePath, string packagePath, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE interactive_execution_assignments
            SET status = 'Preparing', workspace_path = $workspace, runtime_path = $runtime, package_path = $package
            WHERE execution_id = $eid AND execution_attempt_id = $aid;
            """;
        cmd.Parameters.AddWithValue("$workspace", workspacePath);
        cmd.Parameters.AddWithValue("$runtime", runtimePath);
        cmd.Parameters.AddWithValue("$package", packagePath);
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static bool IsTerminal(InteractiveExecutionStatus status) =>
        status is InteractiveExecutionStatus.Completed or InteractiveExecutionStatus.Failed or
            InteractiveExecutionStatus.Cancelled or InteractiveExecutionStatus.TimedOut or InteractiveExecutionStatus.Interrupted;

    private static void Bind(SqliteCommand cmd, InteractiveExecutionAssignment a)
    {
        cmd.Parameters.AddWithValue("$eid", a.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", a.AttemptId);
        cmd.Parameters.AddWithValue("$sid", a.SessionId);
        cmd.Parameters.AddWithValue("$runner", a.SessionRunnerInstanceId);
        cmd.Parameters.AddWithValue("$rid", (object?)a.ReservationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$workspace", (object?)a.WorkspacePath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$runtime", (object?)a.RuntimePath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$package", (object?)a.PackagePath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$status", a.Status.ToString());
        cmd.Parameters.AddWithValue("$created", a.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$started", a.StartedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$completed", a.CompletedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$heartbeat", a.LastHeartbeatAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$cancel", a.CancellationRequestedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$pid", a.ExecutionHostProcessId.HasValue ? a.ExecutionHostProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$exit", a.ExitCode.HasValue ? a.ExitCode.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$ecode", (object?)a.ErrorCode ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$emsg", (object?)a.ErrorMessage ?? DBNull.Value);
    }

    private static async Task<IReadOnlyList<InteractiveExecutionAssignment>> ReadListAsync(SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<InteractiveExecutionAssignment>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            list.Add(Map(reader));
        return list;
    }

    private static InteractiveExecutionAssignment Map(SqliteDataReader r) => new()
    {
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        AttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
        SessionId = r.GetInt32(r.GetOrdinal("session_id")),
        SessionRunnerInstanceId = r.GetString(r.GetOrdinal("session_runner_instance_id")),
        ReservationId = r.IsDBNull(r.GetOrdinal("reservation_id")) ? null : r.GetString(r.GetOrdinal("reservation_id")),
        WorkspacePath = r.IsDBNull(r.GetOrdinal("workspace_path")) ? null : r.GetString(r.GetOrdinal("workspace_path")),
        RuntimePath = r.IsDBNull(r.GetOrdinal("runtime_path")) ? null : r.GetString(r.GetOrdinal("runtime_path")),
        PackagePath = r.IsDBNull(r.GetOrdinal("package_path")) ? null : r.GetString(r.GetOrdinal("package_path")),
        Status = Enum.Parse<InteractiveExecutionStatus>(r.GetString(r.GetOrdinal("status")), true),
        CreatedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("created_at_utc"))),
        StartedAtUtc = r.IsDBNull(r.GetOrdinal("started_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("started_at_utc"))),
        CompletedAtUtc = r.IsDBNull(r.GetOrdinal("completed_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("completed_at_utc"))),
        LastHeartbeatAtUtc = r.IsDBNull(r.GetOrdinal("last_heartbeat_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("last_heartbeat_at_utc"))),
        CancellationRequestedAtUtc = r.IsDBNull(r.GetOrdinal("cancellation_requested_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("cancellation_requested_at_utc"))),
        ExecutionHostProcessId = r.IsDBNull(r.GetOrdinal("execution_host_process_id")) ? null : r.GetInt32(r.GetOrdinal("execution_host_process_id")),
        ExitCode = r.IsDBNull(r.GetOrdinal("exit_code")) ? null : r.GetInt32(r.GetOrdinal("exit_code")),
        ErrorCode = r.IsDBNull(r.GetOrdinal("error_code")) ? null : r.GetString(r.GetOrdinal("error_code")),
        ErrorMessage = r.IsDBNull(r.GetOrdinal("error_message")) ? null : r.GetString(r.GetOrdinal("error_message"))
    };
}
