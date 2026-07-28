using System.Runtime.InteropServices;
using Biason.AutomationAgent.Windows.Interop;
using Microsoft.Extensions.Logging;
using static Biason.AutomationAgent.Windows.Interop.JobObjectNativeMethods;

namespace Biason.AutomationAgent.Windows.Process;

/// <summary>
/// Manages Windows Job Objects for process isolation.
/// All child processes in a Job Object are killed when the object is closed.
/// </summary>
public sealed class JobObjectManager : IDisposable
{
    private readonly ILogger<JobObjectManager> _logger;
    private readonly Dictionary<string, IntPtr> _jobHandles = new();
    private readonly object _lock = new();

    public JobObjectManager(ILogger<JobObjectManager> logger) => _logger = logger;

    /// <summary>Create a Job Object with kill-on-close and optional memory limit.</summary>
    public IntPtr CreateJobObject(string name, long? memoryLimitMb = null, int? maxProcesses = null)
    {
        var handle = JobObjectNativeMethods.CreateJobObject(IntPtr.Zero, $"BiasonAgent_{name}");
        if (handle == IntPtr.Zero)
        {
            var error = Marshal.GetLastWin32Error();
            throw new InvalidOperationException($"Failed to create Job Object: Win32 error {error}");
        }

        // Configure: kill all processes when job handle is closed
        var extInfo = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        extInfo.BasicLimitInformation.LimitFlags = LimitFlags.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

        if (memoryLimitMb.HasValue)
        {
            extInfo.BasicLimitInformation.LimitFlags |= LimitFlags.JOB_OBJECT_LIMIT_JOB_MEMORY;
            extInfo.JobMemoryLimit = (UIntPtr)(memoryLimitMb.Value * 1024 * 1024);
        }

        if (maxProcesses.HasValue)
        {
            extInfo.BasicLimitInformation.LimitFlags |= LimitFlags.JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
            extInfo.BasicLimitInformation.ActiveProcessLimit = (uint)maxProcesses.Value;
        }

        var infoSize = (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
        var infoPtr = Marshal.AllocHGlobal((int)infoSize);
        try
        {
            Marshal.StructureToPtr(extInfo, infoPtr, false);
            if (!SetInformationJobObject(handle, JobObjectInfoType.ExtendedLimitInformation, infoPtr, infoSize))
            {
                var error = Marshal.GetLastWin32Error();
                CloseHandle(handle);
                throw new InvalidOperationException($"Failed to set Job Object limits: Win32 error {error}");
            }
        }
        finally
        {
            Marshal.FreeHGlobal(infoPtr);
        }

        lock (_lock) { _jobHandles[name] = handle; }
        _logger.LogInformation("Created Job Object {Name} (memoryLimit={MemoryMb}MB, maxProcs={MaxProcs})",
            name, memoryLimitMb, maxProcesses);

        return handle;
    }

    /// <summary>Assign a process to an existing Job Object.</summary>
    public bool AssignProcess(IntPtr jobHandle, System.Diagnostics.Process process)
    {
        if (!AssignProcessToJobObject(jobHandle, process.Handle))
        {
            var error = Marshal.GetLastWin32Error();
            _logger.LogError("Failed to assign PID {Pid} to Job Object: Win32 error {Error}", process.Id, error);
            return false;
        }
        _logger.LogDebug("Assigned PID {Pid} to Job Object", process.Id);
        return true;
    }

    /// <summary>Terminate all processes in a Job Object.</summary>
    public void TerminateJobObject(string name, uint exitCode = 1)
    {
        lock (_lock)
        {
            if (!_jobHandles.TryGetValue(name, out var handle)) return;
            JobObjectNativeMethods.TerminateJobObject(handle, exitCode);
            _logger.LogInformation("Terminated all processes in Job Object {Name}", name);
        }
    }

    /// <summary>Close and release a Job Object handle (kills all assigned processes).</summary>
    public void CloseJobObject(string name)
    {
        lock (_lock)
        {
            if (!_jobHandles.Remove(name, out var handle)) return;
            CloseHandle(handle);
            _logger.LogInformation("Closed Job Object {Name}", name);
        }
    }

    /// <summary>Get peak memory usage for a Job Object.</summary>
    public long? GetPeakJobMemoryMb(IntPtr jobHandle)
    {
        try
        {
            var size = (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            var ptr = Marshal.AllocHGlobal((int)size);
            try
            {
                if (QueryInformationJobObject(jobHandle, JobObjectInfoType.ExtendedLimitInformation, ptr, size, out _))
                {
                    var info = Marshal.PtrToStructure<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>(ptr);
                    return (long)info.PeakJobMemoryUsed / (1024 * 1024);
                }
            }
            finally { Marshal.FreeHGlobal(ptr); }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to query Job Object memory");
        }
        return null;
    }

    public void Dispose()
    {
        lock (_lock)
        {
            foreach (var (name, handle) in _jobHandles)
            {
                try { CloseHandle(handle); }
                catch { /* best effort */ }
            }
            _jobHandles.Clear();
        }
    }
}
