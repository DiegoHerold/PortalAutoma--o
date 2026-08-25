using Biason.AutomationAgent.ExecutionHost.Protocol;

namespace Biason.AutomationAgent.ExecutionHost;

/// <summary>
/// Validates the <see cref="PathsConfig"/> ExecutionHost receives before it
/// dares touch the filesystem or hand control to <c>RuntimeLauncher</c>.
///
/// Pulled out of <c>Program.cs</c> (where it used to be a top-level-statement
/// local function) specifically so it can be unit tested directly - a local
/// function inside top-level statements compiles to a compiler-mangled
/// private method (e.g. <c>&lt;&lt;Main&gt;$&gt;g__ValidatePaths|0_1</c>) that
/// is impractical to reach via reflection and was never actually covered by
/// a test, which is exactly how the regression below shipped unnoticed.
/// </summary>
public static class ExecutionHostPathValidator
{
    /// <summary>
    /// Regressao: powershell_script e executable rodam com binarios ja
    /// instalados na maquina (pwsh.exe/powershell.exe) ou empacotados dentro
    /// do proprio pacote (o .exe do entrypoint) - de proposito NAO exigem
    /// uma entrada no Runtime Store (ver ExecutionManager.RequiresManagedRuntime
    /// em Agent.Application), entao RuntimePath vem vazio para esses dois
    /// tipos, por design. Esta validacao, que roda DENTRO do ExecutionHost.exe
    /// (um segundo gate, independente do Agent.Service que lanca o processo),
    /// exigia RuntimePath incondicionalmente para QUALQUER entrypoint e
    /// derrubava o processo com "Missing required path: RuntimePath" (exit
    /// code 2) ANTES mesmo de chegar no RuntimeLauncher - que ja sabia lidar
    /// com RuntimePath vazio. A correcao em ExecutionManager.cs resolvia o
    /// problema no processo que decide lancar a execucao, mas nao esse
    /// segundo gate dentro do processo lancado - por isso so aparecia
    /// rodando de verdade contra o ExecutionHost.exe real (nunca nos testes
    /// unitarios, que chamam ExecutionManager.ExecuteAsync ou
    /// RuntimeLauncher.BuildStartInfo direto, pulando esta validacao).
    /// </summary>
    public static void Validate(PathsConfig paths, string entrypointType)
    {
        var required = new List<(string Name, string Path)>
        {
            ("PackagePath", paths.PackagePath),
            ("WorkspacePath", paths.WorkspacePath),
        };

        if (RequiresManagedRuntime(entrypointType))
            required.Add(("RuntimePath", paths.RuntimePath));

        foreach (var (name, path) in required)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new InvalidOperationException($"Missing required path: {name}");
            if (!Directory.Exists(path))
                throw new InvalidOperationException($"Path does not exist: {name}={path}");
        }

        Directory.CreateDirectory(paths.InputPath);
        Directory.CreateDirectory(paths.OutputPath);
        Directory.CreateDirectory(paths.ArtifactsPath);
        Directory.CreateDirectory(paths.TempPath);
        Directory.CreateDirectory(paths.LogsPath);
    }

    public static bool RequiresManagedRuntime(string? entrypointType) =>
        (entrypointType ?? string.Empty).ToLowerInvariant() switch
        {
            "powershellscript" or "powershell_script" => false,
            "executable" => false,
            _ => true
        };
}
