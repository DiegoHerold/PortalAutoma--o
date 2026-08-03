using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Application.Sessions;

public sealed class InteractiveExecutionTokenService : IInteractiveExecutionTokenService
{
    private readonly Dictionary<string, InteractiveExecutionToken> _tokensByFingerprint = new(StringComparer.Ordinal);
    private readonly object _lock = new();

    public InteractiveExecutionToken Issue(string executionId, string executionAttemptId, int sessionId, string sessionRunnerInstanceId, DateTime expiresAtUtc)
    {
        var token = SessionTokenHasher.NewToken("exec_token");
        var model = new InteractiveExecutionToken
        {
            Token = token,
            Fingerprint = SessionTokenHasher.Fingerprint(token),
            ExecutionId = executionId,
            ExecutionAttemptId = executionAttemptId,
            SessionId = sessionId,
            SessionRunnerInstanceId = sessionRunnerInstanceId,
            ExpiresAtUtc = expiresAtUtc
        };

        lock (_lock) { _tokensByFingerprint[model.Fingerprint] = model; }
        return model;
    }

    public void Remember(InteractiveExecutionToken token)
    {
        lock (_lock) { _tokensByFingerprint[token.Fingerprint] = token; }
    }

    public bool Validate(string token, string executionId, string executionAttemptId, int sessionId, string sessionRunnerInstanceId, DateTime nowUtc)
    {
        var fingerprint = SessionTokenHasher.Fingerprint(token);
        lock (_lock)
        {
            return _tokensByFingerprint.TryGetValue(fingerprint, out var model) &&
                   model.ExpiresAtUtc > nowUtc &&
                   model.ExecutionId == executionId &&
                   model.ExecutionAttemptId == executionAttemptId &&
                   model.SessionId == sessionId &&
                   model.SessionRunnerInstanceId == sessionRunnerInstanceId;
        }
    }

    public void Expire(string token)
    {
        var fingerprint = SessionTokenHasher.Fingerprint(token);
        lock (_lock) { _tokensByFingerprint.Remove(fingerprint); }
    }
}
