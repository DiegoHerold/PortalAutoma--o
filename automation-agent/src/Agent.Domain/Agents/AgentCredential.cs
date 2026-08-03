namespace Biason.AutomationAgent.Domain.Agents;

/// <summary>
/// Credencial do Agent junto ao Portal.
///
/// O valor em texto puro só existe em memória e nunca é persistido diretamente:
/// o <c>IAgentCredentialStore</c> grava apenas a forma protegida (DPAPI no Windows).
/// </summary>
public sealed class AgentCredential
{
    public string Type { get; init; } = "client_token";

    /// <summary>Segredo em texto puro. Nunca serializar, logar ou exportar.</summary>
    public string Value { get; init; } = default!;

    public DateTime? ExpiresAtUtc { get; init; }

    public DateTime StoredAtUtc { get; init; }

    public bool IsExpired(DateTime nowUtc) => ExpiresAtUtc is not null && ExpiresAtUtc <= nowUtc;

    /// <summary>True quando a credencial está perto de expirar e convém rotacionar.</summary>
    public bool NeedsRotation(DateTime nowUtc, TimeSpan threshold) =>
        ExpiresAtUtc is not null && ExpiresAtUtc - nowUtc <= threshold;

    /// <summary>
    /// Representação segura para logs e diagnóstico. Nunca inclui o segredo.
    /// </summary>
    public override string ToString() =>
        $"AgentCredential(type={Type}, expires_at={ExpiresAtUtc:o}, value=***)";
}

/// <summary>
/// Metadados não sensíveis da credencial. É isto — e só isto — que vai
/// para <c>agent_credentials_metadata</c> e para o diagnóstico.
/// </summary>
public sealed class AgentCredentialMetadata
{
    public string Type { get; init; } = "client_token";
    public DateTime? ExpiresAtUtc { get; init; }
    public DateTime StoredAtUtc { get; init; }
    public DateTime? LastUsedAtUtc { get; init; }
    public DateTime? RevokedAtUtc { get; init; }

    /// <summary>Fingerprint SHA-256 truncado, para correlação sem expor o segredo.</summary>
    public string? Fingerprint { get; init; }

    public bool IsRevoked => RevokedAtUtc is not null;
}
