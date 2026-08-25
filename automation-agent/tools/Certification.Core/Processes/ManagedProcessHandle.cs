namespace Biason.AutomationAgent.Certification.Core.Processes;

public sealed class ManagedProcessHandle
{
    public required string Name { get; init; }
    public required int ProcessId { get; init; }
    public required DateTime StartedAtUtc { get; init; }
    public required string StdoutPath { get; init; }
    public required string StderrPath { get; init; }
    public required string PidFilePath { get; init; }

    /// <summary>
    /// True if this process was launched via <see cref="NativeProcess"/> with
    /// CREATE_NEW_PROCESS_GROUP, meaning <see cref="NativeProcess.TrySendGracefulStop"/>
    /// can target it. False means it was launched through the plain
    /// <see cref="System.Diagnostics.Process"/> fallback and can only be
    /// force-killed — see CertificationProcessSupervisor.StartAsync.
    /// </summary>
    public required bool SupportsGracefulStop { get; init; }

    internal nint NativeProcessHandle { get; init; }
}

public sealed record StopResult(bool GracefulShutdownAttempted, bool ForcedTermination, TimeSpan Duration, int? ExitCode);
