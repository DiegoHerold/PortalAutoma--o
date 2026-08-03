using Biason.AutomationAgent.Domain.Models.Execution;
// Ver ILauncher.cs: alias necessário por colisão com System.Threading.ExecutionContext.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IProcessManager
{
    /// <summary>Launch an ExecutionHost process inside a Job Object.</summary>
    Task<ProcessHandle> LaunchAsync(ExecutionContext context, CancellationToken ct = default);

    /// <summary>Terminate a process tree gracefully, then forcefully.</summary>
    Task TerminateAsync(ProcessHandle handle, int gracefulTimeoutMs, CancellationToken ct = default);

    /// <summary>Check if process is still running.</summary>
    bool IsRunning(ProcessHandle handle);
}

public sealed class ProcessHandle
{
    public int ProcessId { get; init; }
    public IntPtr JobObjectHandle { get; init; }
    public string PipeName { get; init; } = default!;
    public System.Diagnostics.Process Process { get; init; } = default!;
}
