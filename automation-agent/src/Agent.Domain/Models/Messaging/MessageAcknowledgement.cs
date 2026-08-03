namespace Biason.AutomationAgent.Domain.Models.Messaging;

public sealed class MessageAcknowledgement
{
    public string MessageId { get; init; } = default!;
    public string Direction { get; init; } = default!;
    public string Status { get; init; } = default!;
    public DateTime AcknowledgedAtUtc { get; init; }
    public string? Detail { get; init; }
}
