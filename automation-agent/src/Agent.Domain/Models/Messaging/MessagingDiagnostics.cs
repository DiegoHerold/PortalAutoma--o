namespace Biason.AutomationAgent.Domain.Models.Messaging;

public sealed class MessagingDiagnostics
{
    public OutboxDiagnostics Outbox { get; init; } = new();
    public InboxDiagnostics Inbox { get; init; } = new();
}

public sealed class OutboxDiagnostics
{
    public int Pending { get; init; }
    public int Failed { get; init; }
    public int Sent { get; init; }
    public int Acknowledged { get; init; }
    public int DeadLetter { get; init; }
}

public sealed class InboxDiagnostics
{
    public int Pending { get; init; }
    public int Processing { get; init; }
    public int Processed { get; init; }
    public int DeadLetter { get; init; }
}
