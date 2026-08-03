using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
// Ver ILauncher.cs: alias necessário por colisão com System.Threading.ExecutionContext.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Application.Launchers;

public sealed class PythonFunctionLauncher : ILauncher
{
    public EntrypointType SupportedType => EntrypointType.PythonFunction;

    public LaunchSpec BuildLaunchSpec(ExecutionContext context)
    {
        var pythonExe = Path.Combine(context.RuntimePath, "python.exe");
        var module = context.Manifest.Entrypoint.Module!;
        var callable = context.Manifest.Entrypoint.Callable!;

        // python -c "import module; module.callable()"
        var script = $"import sys; sys.path.insert(0, r'{context.PackagePath}'); import {module}; {module}.{callable}()";

        return new LaunchSpec
        {
            ExecutablePath = pythonExe,
            Arguments = $"-c \"{script}\"",
            WorkingDirectory = context.WorkspacePath,
            EnvironmentVariables = new Dictionary<string, string>(context.EnvironmentVariables)
        };
    }
}
