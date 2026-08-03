using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveExecutionTokenService
{
    InteractiveExecutionToken Issue(string executionId, string executionAttemptId, int sessionId, string sessionRunnerInstanceId, DateTime expiresAtUtc);
    void Remember(InteractiveExecutionToken token);
    bool Validate(string token, string executionId, string executionAttemptId, int sessionId, string sessionRunnerInstanceId, DateTime nowUtc);
    void Expire(string token);
}
