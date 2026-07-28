using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class AgentStateManagerImpl : IAgentStateManager
{
    private readonly SqliteDatabaseManager _db;
    private readonly IClock _clock;
    private readonly ILogger<AgentStateManagerImpl> _logger;
    private AgentState _currentState = AgentState.Starting;
    private AgentState? _previousState;
    private readonly object _lock = new();

    public AgentState CurrentState
    {
        get { lock (_lock) return _currentState; }
    }

    public AgentState? PreviousState
    {
        get { lock (_lock) return _previousState; }
    }

    public AgentStateManagerImpl(SqliteDatabaseManager db, IClock clock, ILogger<AgentStateManagerImpl> logger)
    {
        _db = db;
        _clock = clock;
        _logger = logger;
    }

    public async Task LoadPersistedStateAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT current_state, previous_state FROM agent_state WHERE id = 1;";
        using var reader = await cmd.ExecuteReaderAsync(ct);
        if (await reader.ReadAsync(ct))
        {
            var persisted = Enum.Parse<AgentState>(reader.GetString(0), ignoreCase: true);
            var prev = reader.IsDBNull(1) ? (AgentState?)null : Enum.Parse<AgentState>(reader.GetString(1), ignoreCase: true);
            lock (_lock)
            {
                // On restart, we always start from Starting regardless of persisted state
                _previousState = persisted;
                _currentState = AgentState.Starting;
            }
            _logger.LogInformation("Loaded persisted state: {PersistedState}, restarting from Starting", persisted);
        }
    }

    public async Task TransitionToAsync(AgentState newState, string? reason = null, string? details = null, string? source = null, CancellationToken ct = default)
    {
        AgentState fromState;
        lock (_lock)
        {
            fromState = _currentState;
        }

        AgentStateMachine.ValidateTransition(fromState, newState);

        var now = _clock.UtcNow;

        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();
        try
        {
            // Upsert agent_state
            var stateCmd = conn.CreateCommand();
            stateCmd.Transaction = tx;
            stateCmd.CommandText = """
                INSERT INTO agent_state (id, current_state, previous_state, last_transition_utc, reason, details)
                VALUES (1, $cs, $ps, $lt, $r, $d)
                ON CONFLICT(id) DO UPDATE SET
                    current_state = $cs,
                    previous_state = $ps,
                    last_transition_utc = $lt,
                    reason = $r,
                    details = $d;
                """;
            stateCmd.Parameters.AddWithValue("$cs", newState.ToString());
            stateCmd.Parameters.AddWithValue("$ps", fromState.ToString());
            stateCmd.Parameters.AddWithValue("$lt", now.ToString("o"));
            stateCmd.Parameters.AddWithValue("$r", (object?)reason ?? DBNull.Value);
            stateCmd.Parameters.AddWithValue("$d", (object?)details ?? DBNull.Value);
            await stateCmd.ExecuteNonQueryAsync(ct);

            // Record transition
            var histCmd = conn.CreateCommand();
            histCmd.Transaction = tx;
            histCmd.CommandText = """
                INSERT INTO agent_state_transitions (from_state, to_state, reason, details, source, transitioned_at_utc)
                VALUES ($fs, $ts, $r, $d, $src, $t);
                """;
            histCmd.Parameters.AddWithValue("$fs", fromState.ToString());
            histCmd.Parameters.AddWithValue("$ts", newState.ToString());
            histCmd.Parameters.AddWithValue("$r", (object?)reason ?? DBNull.Value);
            histCmd.Parameters.AddWithValue("$d", (object?)details ?? DBNull.Value);
            histCmd.Parameters.AddWithValue("$src", (object?)source ?? DBNull.Value);
            histCmd.Parameters.AddWithValue("$t", now.ToString("o"));
            await histCmd.ExecuteNonQueryAsync(ct);

            tx.Commit();
        }
        catch
        {
            tx.Rollback();
            throw;
        }

        lock (_lock)
        {
            _previousState = fromState;
            _currentState = newState;
        }

        _logger.LogInformation("Agent state: {From} -> {To} (reason: {Reason})", fromState, newState, reason ?? "none");
    }

    public async Task<IReadOnlyList<StateTransitionRecord>> GetTransitionHistoryAsync(int limit = 50, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT id, from_state, to_state, reason, details, source, transitioned_at_utc
            FROM agent_state_transitions
            ORDER BY transitioned_at_utc DESC
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$limit", limit);

        var results = new List<StateTransitionRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
        {
            results.Add(new StateTransitionRecord
            {
                Id = reader.GetInt64(0),
                EntityType = "agent",
                FromState = reader.GetString(1),
                ToState = reader.GetString(2),
                Reason = reader.IsDBNull(3) ? null : reader.GetString(3),
                Details = reader.IsDBNull(4) ? null : reader.GetString(4),
                Source = reader.IsDBNull(5) ? null : reader.GetString(5),
                TransitionedAtUtc = DateTime.Parse(reader.GetString(6))
            });
        }
        return results;
    }
}
