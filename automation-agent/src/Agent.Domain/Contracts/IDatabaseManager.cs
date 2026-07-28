namespace Biason.AutomationAgent.Domain.Contracts;

public interface IDatabaseManager
{
    Task InitializeAsync(CancellationToken ct = default);
    Task<bool> VerifyIntegrityAsync(CancellationToken ct = default);
    long GetDatabaseSizeKb();
}
