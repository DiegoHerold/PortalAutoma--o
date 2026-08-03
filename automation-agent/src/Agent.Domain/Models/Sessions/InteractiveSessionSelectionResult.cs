namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class InteractiveSessionSelectionResult
{
    public bool Success { get; init; }
    public InteractiveSessionRecord? Session { get; init; }
    public string? RejectionCode { get; init; }
    public string? RejectionReason { get; init; }

    public static InteractiveSessionSelectionResult Selected(InteractiveSessionRecord session) =>
        new() { Success = true, Session = session };

    public static InteractiveSessionSelectionResult Rejected(string code, string reason) =>
        new() { Success = false, RejectionCode = code, RejectionReason = reason };
}
