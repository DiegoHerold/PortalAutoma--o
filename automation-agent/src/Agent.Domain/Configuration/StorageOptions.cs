using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class StorageOptions
{
    public const string Section = "Storage";

    [Range(256, int.MaxValue)]
    public long MinimumFreeDiskMb { get; set; } = 2048;
}
