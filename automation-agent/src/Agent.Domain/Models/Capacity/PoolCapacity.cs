namespace Biason.AutomationAgent.Domain.Models.Capacity;

public sealed class PoolCapacity
{
    public int RecommendedTotal { get; init; }
    public int AdministratorTotal { get; init; }
    public int EffectiveTotal { get; init; }
    public int Used { get; set; }
    public int Reserved { get; set; }
    public int Available => Math.Max(0, EffectiveTotal - Used - Reserved);
}
