using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
// Alias necessário: "ExecutionContext" colide com System.Threading.ExecutionContext,
// trazido implicitamente por ImplicitUsings. O alias tem prioridade na resolução
// e desambigua sem precisar renomear o tipo de domínio em todo o codebase.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ILauncher
{
    EntrypointType SupportedType { get; }

    /// <summary>Build the command line and environment for the ExecutionHost to run.</summary>
    LaunchSpec BuildLaunchSpec(ExecutionContext context);
}

public sealed class LaunchSpec
{
    public string ExecutablePath { get; init; } = default!;
    public string Arguments { get; init; } = string.Empty;
    public string WorkingDirectory { get; init; } = default!;
    public Dictionary<string, string> EnvironmentVariables { get; init; } = new();
}
