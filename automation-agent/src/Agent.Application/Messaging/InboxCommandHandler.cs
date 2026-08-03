using Biason.AutomationAgent.Domain.Models.Messaging;

namespace Biason.AutomationAgent.Application.Messaging;

public interface IInboxCommandHandler
{
    string MessageType { get; }
    Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default);
}

public sealed class InboxCommandHandlerResult
{
    private InboxCommandHandlerResult(bool success, bool deadLetter, string? result, string? error)
    {
        Success = success;
        DeadLetter = deadLetter;
        Result = result;
        Error = error;
    }

    public bool Success { get; }
    public bool DeadLetter { get; }
    public string? Result { get; }
    public string? Error { get; }

    public static InboxCommandHandlerResult Processed(string? result = null) =>
        new(success: true, deadLetter: false, result, error: null);

    public static InboxCommandHandlerResult Dead(string error) =>
        new(success: false, deadLetter: true, result: null, error);
}
