namespace Biason.AutomationAgent.Domain.Enums;

public enum ReservationStatus
{
    /// <summary>Slot consumido imediatamente após admissão aceita; tem TTL (Bloco 5.5, seção 9).</summary>
    Temporary,
    /// <summary>Confirmada por execution.commit; não expira mais por TTL (Bloco 5.5, seção 8/14).</summary>
    Committed,
    Released,
    Expired,
    Cancelled
}
