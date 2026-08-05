using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Registration;

/// <summary>Informações mínimas enviadas ao Portal no registro (seção 10).</summary>
public sealed class RegistrationRequest
{
    [JsonPropertyName("installation_id")]
    public string InstallationId { get; init; } = default!;

    [JsonPropertyName("local_identity")]
    public string LocalIdentity { get; init; } = default!;

    [JsonPropertyName("machine_fingerprint")]
    public string? MachineFingerprint { get; init; }

    [JsonPropertyName("hostname")]
    public string Hostname { get; init; } = default!;

    [JsonPropertyName("agent_version")]
    public string AgentVersion { get; init; } = default!;

    [JsonPropertyName("operating_system")]
    public string? OperatingSystem { get; init; }

    [JsonPropertyName("architecture")]
    public string? Architecture { get; init; }

    /// <summary>
    /// Token de uso limitado, configurado na instalação. Nunca é persistido junto
    /// da credencial definitiva e nunca aparece em logs ou diagnóstico.
    /// </summary>
    [JsonPropertyName("registration_token")]
    public string RegistrationToken { get; init; } = default!;
}

public sealed class RegistrationOsInfo
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = default!;

    [JsonPropertyName("architecture")]
    public string Architecture { get; init; } = default!;
}

public sealed class RegistrationResponse
{
    [JsonPropertyName("agent_id")]
    public string? AgentId { get; init; }

    [JsonPropertyName("agent")]
    public RegistrationAgent? Agent { get; init; }

    [JsonPropertyName("credential")]
    public RegistrationCredential Credential { get; init; } = default!;

    [JsonPropertyName("portal")]
    public RegistrationPortalEndpoints? Portal { get; init; }
}

public sealed class RegistrationAgent
{
    [JsonPropertyName("id")]
    public string Id { get; init; } = default!;
}

public sealed class RegistrationCredential
{
    [JsonPropertyName("type")]
    public string Type { get; init; } = "client_token";

    /// <summary>Segredo. Nunca logar, nunca exportar em diagnóstico.</summary>
    [JsonPropertyName("value")]
    public string? Value { get; init; }

    [JsonPropertyName("public_identifier")]
    public string? PublicIdentifier { get; init; }

    [JsonPropertyName("secret")]
    public string? Secret { get; init; }

    [JsonPropertyName("bearer_token")]
    public string? BearerToken { get; init; }

    [JsonPropertyName("expires_at")]
    public DateTime? ExpiresAt { get; init; }
}

public sealed class RegistrationPortalEndpoints
{
    [JsonPropertyName("websocket_url")]
    public string? WebSocketUrl { get; init; }

    [JsonPropertyName("api_base_url")]
    public string? ApiBaseUrl { get; init; }
}

/// <summary>Erro estruturado devolvido pelo Portal quando o registro falha.</summary>
public sealed class RegistrationFailure
{
    [JsonPropertyName("reason_code")]
    public string ReasonCode { get; init; } = "REGISTRATION_FAILED";

    [JsonPropertyName("message")]
    public string? Message { get; init; }

    [JsonPropertyName("retryable")]
    public bool Retryable { get; init; }
}

public static class RegistrationReasonCodes
{
    public const string InvalidToken = "INVALID_REGISTRATION_TOKEN";
    public const string TokenExpired = "REGISTRATION_TOKEN_EXPIRED";
    public const string TokenAlreadyUsed = "REGISTRATION_TOKEN_ALREADY_USED";
    public const string Revoked = "AGENT_REVOKED";
    public const string VersionUnsupported = "AGENT_VERSION_UNSUPPORTED";
    public const string Unreachable = "PORTAL_UNREACHABLE";
    public const string InvalidResponse = "INVALID_PORTAL_RESPONSE";
}
