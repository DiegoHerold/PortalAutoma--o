using System.Diagnostics;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Microsoft.Extensions.Logging;
// Ver ILauncher.cs: alias necessário por colisão com System.Threading.ExecutionContext.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Windows.Process;

public sealed class ProcessTreeManager : IProcessManager
{
    private readonly JobObjectManager _jobManager;
    private readonly IDirectoryResolver _dirs;
    private readonly ILogger<ProcessTreeManager> _logger;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false
    };

    public ProcessTreeManager(
        JobObjectManager jobManager,
        IDirectoryResolver dirs,
        ILogger<ProcessTreeManager> logger)
    {
        _jobManager = jobManager;
        _dirs = dirs;
        _logger = logger;
    }

    public async Task<ProcessHandle> LaunchAsync(ExecutionContext context, CancellationToken ct = default)
    {
        var jobName = $"exec_{context.ExecutionId}_{context.AttemptId}";
        var pipeName = string.IsNullOrWhiteSpace(context.PipeName)
            ? $"biason_agent_{context.ExecutionId}_{context.AttemptId}"
            : context.PipeName!;

        // Create Job Object with memory limit if specified
        long? memLimitMb = context.Manifest.Resources?.MaxMemoryMb;
        var jobHandle = _jobManager.CreateJobObject(jobName, memLimitMb, maxProcesses: 50);

        // Resolve ExecutionHost path
        var executionHostPath = ResolveExecutionHostPath();

        // Write config file (secrets via file, not command line or env vars visible in process list)
        var configPath = await WriteConfigFileAsync(context, pipeName, ct);

        var startInfo = new ProcessStartInfo
        {
            FileName = executionHostPath,
            Arguments = $"--config \"{configPath}\" --pipe \"{pipeName}\"",
            WorkingDirectory = context.WorkspacePath,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        // Minimal env vars (non-secret, for process identification only)
        startInfo.Environment["AUTOMATION_EXECUTION_ID"] = context.ExecutionId;
        startInfo.Environment["AUTOMATION_ATTEMPT_ID"] = context.AttemptId;
        startInfo.Environment["AUTOMATION_PIPE_NAME"] = pipeName;

        var process = new System.Diagnostics.Process { StartInfo = startInfo };

        try
        {
            process.Start();
        }
        catch (Exception ex)
        {
            _jobManager.CloseJobObject(jobName);
            // Clean up config file on failure
            try { File.Delete(configPath); } catch { }
            throw new InvalidOperationException($"Failed to start ExecutionHost: {ex.Message}", ex);
        }

        // Assign to Job Object
        if (!_jobManager.AssignProcess(jobHandle, process))
        {
            _logger.LogWarning("Failed to assign PID {Pid} to Job Object, process may survive agent crash", process.Id);
        }

        _logger.LogInformation("Launched ExecutionHost PID={Pid} for execution {ExecutionId}, pipe={PipeName}",
            process.Id, context.ExecutionId, pipeName);

        var handle = new ProcessHandle
        {
            ProcessId = process.Id,
            JobObjectHandle = jobHandle,
            PipeName = pipeName,
            Process = process
        };

        return handle;
    }

    public async Task TerminateAsync(ProcessHandle handle, int gracefulTimeoutMs, CancellationToken ct = default)
    {
        try
        {
            if (handle.Process.HasExited) return;

            _logger.LogInformation("Requesting graceful shutdown for PID {Pid}", handle.ProcessId);

            var exited = handle.Process.WaitForExit(gracefulTimeoutMs);
            if (!exited)
            {
                _logger.LogWarning("PID {Pid} did not exit gracefully, terminating via Job Object", handle.ProcessId);
                var jobName = $"exec_{handle.PipeName.Replace("biason_agent_", "")}";
                _jobManager.TerminateJobObject(jobName);

                handle.Process.WaitForExit(3000);
            }
        }
        catch (InvalidOperationException)
        {
            // Process already exited
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error terminating PID {Pid}", handle.ProcessId);
        }
    }

    public bool IsRunning(ProcessHandle handle)
    {
        try { return !handle.Process.HasExited; }
        catch { return false; }
    }

    private string ResolveExecutionHostPath()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "AgentService", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "ExecutionHost", "ExecutionHost.exe"),
        };

        // Regressao real, encontrada rodando contra o Agent.Service online (nao
        // em teste unitario nenhum): a ordem fixa da lista acima coloca
        // bin/Debug antes de bin/Release. Um build de Debug de dias atras (de
        // muito antes das correcoes desta sessao) continuava presente no disco
        // e "primeiro que existir" o escolhia sempre, ignorando que o
        // bin/Release tinha acabado de ser recompilado com o codigo corrigido.
        // O ExecutionHost.exe realmente executado ficava permanentemente preso
        // num binario de 6 dias atras - reiniciar o Agent.Service e recompilar
        // a solution em Release nao adiantava nada, porque nenhum dos dois
        // mexe em qual arquivo esse metodo escolhe. O stack trace do erro
        // continuava citando codigo que ja tinha sido removido do fonte havia
        // varios commits, o que so fez sentido depois de comparar a data de
        // modificacao dos dois bin/*/ExecutionHost.dll. Corrigido escolhendo,
        // entre os candidatos que existem, o de data de modificacao mais
        // recente - o binario certo vence sempre, independente de qual
        // configuracao (Debug/Release) foi compilada por ultimo ou em que
        // pasta ela mora.
        var resolved = PickNewestExisting(candidates);
        if (resolved is null)
        {
            throw new InvalidOperationException(
                $"ExecutionHost.exe not found. Searched: {string.Join(", ", candidates.Select(Path.GetFullPath))}");
        }

        return Path.GetFullPath(resolved);
    }

    /// <summary>
    /// De todos os caminhos candidatos que realmente existem no disco,
    /// devolve o de data de modificacao mais recente (null se nenhum
    /// existir). Extraido de <see cref="ResolveExecutionHostPath"/> so essa
    /// regra - a parte que realmente importa da correcao - da pra testar
    /// direto com arquivos temporarios reais, sem depender de
    /// AppContext.BaseDirectory nem da estrutura de pastas bin/Debug|Release
    /// do repositorio.
    /// </summary>
    private static string? PickNewestExisting(IEnumerable<string> candidates)
    {
        return candidates
            .Where(File.Exists)
            .Select(path => (Path: path, WriteTimeUtc: File.GetLastWriteTimeUtc(path)))
            .OrderByDescending(c => c.WriteTimeUtc)
            .Select(c => (string?)c.Path)
            .FirstOrDefault();
    }

    private async Task<string> WriteConfigFileAsync(ExecutionContext context, string pipeName, CancellationToken ct)
    {
        var configDir = Path.Combine(context.WorkspacePath, "temp");
        Directory.CreateDirectory(configDir);
        var configPath = Path.Combine(configDir, $"execution_config_{Guid.NewGuid():N}.json");

        var config = new
        {
            execution_id = context.ExecutionId,
            attempt_id = context.AttemptId,
            automation_id = context.AutomationId,
            pipe_name = pipeName,
            token = Guid.NewGuid().ToString("N"),
            timeout_seconds = context.TimeoutSeconds,
            graceful_shutdown_seconds = context.GracefulShutdownSeconds,
            entrypoint = new
            {
                type = context.Manifest.Entrypoint.Type.ToString(),
                // Bug real: isso ficava hardcoded em null, entao TODA
                // automacao do tipo "executable" chegava no ExecutionHost
                // sem o caminho do .exe e falhava com "Executable entrypoint
                // requires 'executable_path'" (RuntimeLauncher.BuildExecutable)
                // - mesmo com um manifest 100% valido. Precisa propagar o
                // Entrypoint.Path (populado pelo ManifestValidator a partir de
                // entrypoint.path no manifest) para o config que o
                // ExecutionHost realmente le.
                executable_path = context.Manifest.Entrypoint.Path,
                arguments = context.Manifest.Entrypoint.Args,
                module = context.Manifest.Entrypoint.Module,
                callable = context.Manifest.Entrypoint.Callable,
                script = context.Manifest.Entrypoint.Script
            },
            paths = new
            {
                runtime_path = context.RuntimePath,
                package_path = context.PackagePath,
                workspace_path = context.WorkspacePath,
                input_path = Path.Combine(context.WorkspacePath, "input"),
                output_path = Path.Combine(context.WorkspacePath, "output"),
                artifacts_path = Path.Combine(context.WorkspacePath, "artifacts"),
                temp_path = Path.Combine(context.WorkspacePath, "temp"),
                logs_path = Path.Combine(context.WorkspacePath, "logs")
            },
            environment = context.EnvironmentVariables
        };

        var json = JsonSerializer.Serialize(config, JsonOpts);
        await File.WriteAllTextAsync(configPath, json, ct);

        return configPath;
    }
}
