using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Application.Launchers;

public sealed class ExecutableLauncher : ILauncher
{
    public EntrypointType SupportedType => EntrypointType.Executable;

    public LaunchSpec BuildLaunchSpec(ExecutionContext context)
    {
        var exePath = Path.Combine(context.PackagePath, context.Manifest.Entrypoint.Path!);
        var args = context.Manifest.Entrypoint.Args ?? string.Empty;

        return new LaunchSpec
        {
            ExecutablePath = exePath,
            Arguments = args,
            WorkingDirectory = context.WorkspacePath,
            EnvironmentVariables = new Dictionary<string, string>(context.EnvironmentVariables)
        };
    }
}
