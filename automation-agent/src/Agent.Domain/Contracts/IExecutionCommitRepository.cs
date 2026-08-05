using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionCommitRepository
{
    /// <summary>
    /// Persiste a tentativa de commit. Deixa a checagem de duplicidade de alto
    /// nível para <see cref="GetAcceptedByAttemptAsync"/> — o índice único do
    /// schema (accepted = 1 por execution_attempt_id) é a última linha de
    /// defesa contra dois commits aceitos concorrentes para a mesma tentativa.
    /// </summary>
    Task SaveAsync(ExecutionCommitRecord commit, CancellationToken ct = default);

    Task<ExecutionCommitRecord?> GetAcceptedByAttemptAsync(string executionAttemptId, CancellationToken ct = default);
}
