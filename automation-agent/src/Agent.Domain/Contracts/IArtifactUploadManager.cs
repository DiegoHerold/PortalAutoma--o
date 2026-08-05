namespace Biason.AutomationAgent.Domain.Contracts;

public interface IArtifactUploadManager
{
    Task<int> ProcessDueAsync(CancellationToken ct = default);
    Task RecoverUploadingAsync(CancellationToken ct = default);
}
