namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Provides real-time CPU usage percentage.
/// </summary>
public interface ICpuUsageProvider
{
    /// <summary>
    /// Returns CPU usage percentage (0-100) since last measurement.
    /// </summary>
    double GetCpuUsagePercent();
}
