namespace Biason.AutomationAgent.Domain.Contracts;

public interface IArtifactContentUploader
{
    Task<PortalArtifactUploadOutcome> UploadAsync(
        PortalArtifactUploadTarget target,
        string localPath,
        string contentType,
        CancellationToken ct = default);
}
