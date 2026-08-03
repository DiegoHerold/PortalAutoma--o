using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
// Ver ILauncher.cs: alias necessário por colisão com System.Threading.ExecutionContext.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Application.Launchers;

public sealed class PythonModuleLauncher : ILauncher
{
    public EntrypointType SupportedType => EntrypointType.PythonModule;

    public LaunchSpec BuildLaunchSpec(ExecutionContext context)
    {
        var pythonExe = Path.Combine(context.RuntimePath, "python.exe");
        var module = context.Manifest.Entrypoint.Module!;

        var env = new Dictionary<string, string>(context.EnvironmentVariables);
        env["PYTHONPATH"] = context.PackagePath;

        return new LaunchSpec
        {
            ExecutablePath = pythonExe,
            Arguments = $"-m {module}",
            WorkingDirectory = context.WorkspacePath,
            EnvironmentVariables = env
        };
    }
}
