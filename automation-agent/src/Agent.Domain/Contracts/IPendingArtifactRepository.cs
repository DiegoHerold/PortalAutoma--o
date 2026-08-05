using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IPendingArtifactRepository
{
    Task SaveAsync(PendingArtifactRecord artifact, CancellationToken ct = default);
    Task<PendingArtifactRecord?> GetAsync(string artifactId, CancellationToken ct = default);
    Task<IReadOnlyList<PendingArtifactRecord>> GetUploadCandidatesAsync(DateTime nowUtc, int limit, CancellationToken ct = default);
    Task<IReadOnlyList<PendingArtifactRecord>> GetNonFinalAsync(int limit = 100, CancellationToken ct = default);
    Task SetAnnouncementAsync(string artifactId, string messageId, ArtifactStatus status, CancellationToken ct = default);
    Task SetUploadInstructionsAsync(
        string artifactId,
        string uploadSessionId,
        string uploadUrl,
        string uploadMethod,
        string? uploadHeadersJson,
        DateTime? uploadExpiresAtUtc,
        DateTime availableAtUtc,
        CancellationToken ct = default);
    Task SetUploadedMessageAsync(
        string artifactId,
        string messageId,
        ArtifactStatus status,
        DateTime uploadedAtUtc,
        string? remoteObjectId,
        string? lastError,
        CancellationToken ct = default);
    Task SetFailedMessageAsync(string artifactId, string messageId, CancellationToken ct = default);
    Task UpdateStatusAsync(
        string artifactId,
        ArtifactStatus status,
        DateTime? availableAtUtc,
        DateTime? uploadedAtUtc,
        DateTime? confirmedAtUtc,
        string? remoteObjectId,
        int attemptCount,
        string? lastError,
        CancellationToken ct = default);
    Task<PendingArtifactDiagnostics> GetDiagnosticsAsync(CancellationToken ct = default);
}
