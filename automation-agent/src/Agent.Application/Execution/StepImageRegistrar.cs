using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Microsoft.Extensions.Logging;
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Application.Execution;

/// <summary>
/// Imagem do passo no modo agente (contracts/automation-events/v1): o SDK grava
/// <c>artifacts/passos/&lt;imagem_id&gt;.jpg</c> e depois emite o <c>passo</c>. Ao ver o passo,
/// o Agent registra o arquivo para subir já, pelo mesmo caminho dos artefatos (HTTPS,
/// nunca pelo WebSocket). O id do artefato sai da tentativa e da imagem: registrar de novo,
/// mesmo depois de um reinício do Agent, não duplica.
/// </summary>
public sealed class StepImageRegistrar
{
    public const string Folder = "passos";
    private static readonly Regex ImageIdPattern = new("^[A-Za-z0-9_-]{1,80}$", RegexOptions.Compiled | RegexOptions.CultureInvariant);

    private readonly IArtifactManager _artifacts;
    private readonly ILogger<StepImageRegistrar> _logger;
    private readonly ConcurrentDictionary<string, byte> _registered = new(StringComparer.Ordinal);

    public StepImageRegistrar(IArtifactManager artifacts, ILogger<StepImageRegistrar> logger)
    {
        _artifacts = artifacts;
        _logger = logger;
    }

    public async Task<bool> TryRegisterAsync(ExecutionContext context, JsonElement automationEvent, CancellationToken ct = default)
    {
        if (!TryGetImageId(automationEvent, out var imageId))
            return false;

        var key = context.AttemptId + "/" + imageId;
        if (!_registered.TryAdd(key, 0))
            return false;

        var path = Path.Combine(context.WorkspacePath, "artifacts", Folder, imageId + ".jpg");
        if (!File.Exists(path))
        {
            _registered.TryRemove(key, out _);
            _logger.LogWarning("Passo {ImageId} sem o arquivo da imagem em {Path}.", imageId, path);
            return false;
        }

        string sha256;
        long size;
        await using (var stream = File.OpenRead(path))
        {
            sha256 = Convert.ToHexString(await SHA256.HashDataAsync(stream, ct)).ToLowerInvariant();
            size = stream.Length;
        }

        await _artifacts.RegisterAsync(context.ExecutionId, context.AttemptId, new[]
        {
            new ExecutionArtifactRef
            {
                ArtifactId = ArtifactIdFor(context.AttemptId, imageId),
                Name = Folder + "/" + imageId + ".jpg",
                ContentType = "image/jpeg",
                SizeBytes = size,
                Sha256 = sha256,
                LocalPath = path
            }
        }, ct);
        return true;
    }

    public static string ArtifactIdFor(string attemptId, string imageId)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(attemptId + "/" + imageId));
        return "art_" + Convert.ToHexString(hash).ToLowerInvariant()[..32];
    }

    public static bool TryGetImageId(JsonElement automationEvent, out string imageId)
    {
        imageId = string.Empty;
        if (automationEvent.ValueKind != JsonValueKind.Object ||
            !automationEvent.TryGetProperty("type", out var type) || type.ValueKind != JsonValueKind.String ||
            type.GetString() != "passo" ||
            !automationEvent.TryGetProperty("payload", out var payload) || payload.ValueKind != JsonValueKind.Object ||
            !payload.TryGetProperty("imagem_id", out var id) || id.ValueKind != JsonValueKind.String)
            return false;

        var value = id.GetString() ?? string.Empty;
        if (!ImageIdPattern.IsMatch(value))
            return false;
        imageId = value;
        return true;
    }
}
