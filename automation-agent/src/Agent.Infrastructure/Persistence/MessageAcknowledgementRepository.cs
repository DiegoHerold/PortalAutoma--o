using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class MessageAcknowledgementRepository : IMessageAcknowledgementRepository
{
    private readonly SqliteDatabaseManager _db;

    public MessageAcknowledgementRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(MessageAcknowledgement acknowledgement, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO message_acknowledgements
                (message_id, direction, status, acknowledged_at_utc, detail)
            VALUES
                ($message_id, $direction, $status, $acknowledged_at, $detail)
            ON CONFLICT(message_id) DO UPDATE SET
                direction = excluded.direction,
                status = excluded.status,
                acknowledged_at_utc = excluded.acknowledged_at_utc,
                detail = excluded.detail;
            """;
        cmd.Parameters.AddWithValue("$message_id", acknowledgement.MessageId);
        cmd.Parameters.AddWithValue("$direction", acknowledgement.Direction);
        cmd.Parameters.AddWithValue("$status", acknowledgement.Status);
        cmd.Parameters.AddWithValue("$acknowledged_at", acknowledgement.AcknowledgedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$detail", (object?)acknowledgement.Detail ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }
}
