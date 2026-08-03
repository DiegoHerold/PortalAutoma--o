namespace Biason.AutomationAgent.Domain.Identity;

/// <summary>
/// Identidade persistente do Agent.
///
/// Declarado como <c>record</c> porque <see cref="Infrastructure"/> usa expressões
/// <c>with</c> para trocar o <see cref="InstanceId"/> (que é volátil por processo)
/// sem reler o banco. Expressões <c>with</c> não são válidas em classes comuns.
/// </summary>
public sealed record AgentIdentity
{
    /// <summary>Identificador estável da instalação, gerado localmente no primeiro boot.</summary>
    public string InstallationId { get; init; } = default!;

    /// <summary>Identificador atribuído pelo Portal no registro. Nulo enquanto não registrado.</summary>
    public string? AgentId { get; set; }

    /// <summary>Fingerprint da máquina, derivado de hostname e hardware.</summary>
    public string MachineId { get; init; } = default!;

    /// <summary>Identificador do processo atual. Muda a cada reinicialização do serviço.</summary>
    public string InstanceId { get; init; } = default!;

    public DateTime CreatedAtUtc { get; init; }

    public DateTime? RegisteredAtUtc { get; set; }

    /// <summary>True quando o Portal já atribuiu um <see cref="AgentId"/>.</summary>
    public bool IsRegistered => !string.IsNullOrWhiteSpace(AgentId);
}
