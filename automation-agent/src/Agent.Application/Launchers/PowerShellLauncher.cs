using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Application.Launchers;

public sealed class PowerShellLauncher : ILauncher
{
    public EntrypointType SupportedType => EntrypointType.PowerShellScript;

    public LaunchSpec BuildLaunchSpec(ExecutionContext context)
    {
        var scriptPath = Path.Combine(context.PackagePath, context.Manifest.Entrypoint.Script!);

        return new LaunchSpec
        {
            ExecutablePath = "pwsh.exe",
            Arguments = $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"{scriptPath}\"",
            WorkingDirectory = context.WorkspacePath,
            EnvironmentVariables = new Dictionary<string, string>(context.EnvironmentVariables)
        };
    }
}
