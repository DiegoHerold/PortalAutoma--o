using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
// Ver ILauncher.cs: alias necessário por colisão com System.Threading.ExecutionContext.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Application.Launchers;

public sealed class PowerShellLauncher : ILauncher
{
    public EntrypointType SupportedType => EntrypointType.PowerShellScript;

    public LaunchSpec BuildLaunchSpec(ExecutionContext context)
    {
        var scriptPath = Path.Combine(context.PackagePath, context.Manifest.Entrypoint.Script!);

        return new LaunchSpec
        {
            ExecutablePath = ResolvePowerShellExecutable(),
            Arguments = $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"{scriptPath}\"",
            WorkingDirectory = context.WorkspacePath,
            EnvironmentVariables = new Dictionary<string, string>(context.EnvironmentVariables)
        };
    }

    // PowerShell 7+ (pwsh.exe) e um instalador separado - nem toda maquina
    // Windows o tem. Hardcodar "pwsh.exe" bloqueava toda automacao
    // powershell_script em qualquer maquina sem PowerShell 7 instalado, com
    // um erro de "arquivo nao encontrado" so na hora de lancar o processo.
    // Windows PowerShell 5.1 (powershell.exe) vem embutido em toda
    // instalacao do Windows e aceita os mesmos parametros usados aqui, entao
    // usamos como fallback em vez de falhar a execucao.
    public static string ResolvePowerShellExecutable()
    {
        if (IsOnPath("pwsh.exe"))
            return "pwsh.exe";

        var programFilesCandidate = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            "PowerShell", "7", "pwsh.exe");
        if (File.Exists(programFilesCandidate))
            return programFilesCandidate;

        return "powershell.exe";
    }

    private static bool IsOnPath(string fileName)
    {
        var pathVar = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        foreach (var dir in pathVar.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            string candidate;
            try
            {
                candidate = Path.Combine(dir.Trim('"'), fileName);
            }
            catch (ArgumentException)
            {
                continue; // entrada invalida no PATH, ignora
            }

            if (File.Exists(candidate))
                return true;
        }

        return false;
    }
}
