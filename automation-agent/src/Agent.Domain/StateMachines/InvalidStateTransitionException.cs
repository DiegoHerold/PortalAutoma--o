namespace Biason.AutomationAgent.Domain.StateMachines;

public sealed class InvalidStateTransitionException : InvalidOperationException
{
    public string FromState { get; }
    public string ToState { get; }

    public InvalidStateTransitionException(string from, string to)
        : base($"Invalid state transition from '{from}' to '{to}'.")
    {
        FromState = from;
        ToState = to;
    }
}
