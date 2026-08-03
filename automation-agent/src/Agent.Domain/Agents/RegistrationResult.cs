namespace Biason.AutomationAgent.Domain.Agents;

public enum RegistrationOutcome
{
    /// <summary>Já havia registro válido; nada foi enviado ao Portal.</summary>
    AlreadyRegistered,

    /// <summary>Registro concluído agora; agent_id e credencial persistidos.</summary>
    Registered,

    /// <summary>Portal rejeitou o registro. Ver <see cref="RegistrationResult.ReasonCode"/>.</summary>
    Rejected,

    /// <summary>Falha transitória (rede, timeout). Pode ser repetido.</summary>
    Failed,

    /// <summary>Sem token de registro configurado — o Agent opera apenas localmente.</summary>
    NotConfigured
}

public sealed record RegistrationResult(
    RegistrationOutcome Outcome,
    string? AgentId = null,
    string? ReasonCode = null,
    string? Message = null,
    bool Retryable = false)
{
    public bool IsRegistered => Outcome is RegistrationOutcome.Registered or RegistrationOutcome.AlreadyRegistered;

    public static RegistrationResult AlreadyRegistered(string agentId) =>
        new(RegistrationOutcome.AlreadyRegistered, agentId);

    public static RegistrationResult Registered(string agentId) =>
        new(RegistrationOutcome.Registered, agentId);

    public static RegistrationResult Rejected(string reasonCode, string? message, bool retryable = false) =>
        new(RegistrationOutcome.Rejected, null, reasonCode, message, retryable);

    public static RegistrationResult Failed(string reasonCode, string? message) =>
        new(RegistrationOutcome.Failed, null, reasonCode, message, Retryable: true);

    public static RegistrationResult NotConfigured() =>
        new(RegistrationOutcome.NotConfigured, null, "NO_REGISTRATION_TOKEN",
            "Nenhum token de registro configurado.");
}
