using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Biason.AutomationAgent.ExecutionHost.Protocol;

namespace Biason.AutomationAgent.ExecutionHost.Launchers;

/// <summary>
/// Launches the actual automation process based on the entrypoint type.
/// Builds the appropriate command line for Python, PowerShell, executables, or Playwright.
/// </summary>
public static class RuntimeLauncher
{
    public static ProcessStartInfo BuildStartInfo(ExecutionConfig config)
    {
        return config.Entrypoint.Type.ToLowerInvariant() switch
        {
            "pythonfunction" or "python_function" => BuildPythonFunction(config),
            "pythonmodule" or "python_module" => BuildPythonModule(config),
            "powershellscript" or "powershell_script" => BuildPowerShell(config),
            "executable" => BuildExecutable(config),
            "browserplaywright" or "browser_playwright" => BuildBrowserPlaywright(config),
            "pythondesktop" or "python_desktop" => BuildPythonDesktop(config),
            _ => throw new InvalidOperationException($"Unsupported entrypoint type: {config.Entrypoint.Type}")
        };
    }

    private static ProcessStartInfo BuildPythonFunction(ExecutionConfig config)
    {
        var pythonExe = config.Entrypoint.ExecutablePath
            ?? Path.Combine(config.Paths.RuntimePath, "python.exe");

        var module = config.Entrypoint.Module
            ?? throw new InvalidOperationException("Python function entrypoint requires 'module'");
        var callable = config.Entrypoint.Callable ?? "run";

        var bootstrap = BuildPythonFunctionBootstrap(module, callable);
        var psi = CreateBase(config, pythonExe, $"-u -c \"{EncodeBootstrap(bootstrap)}\"");
        psi.Environment["AUTOMATION_PACKAGE_PATH"] = config.Paths.PackagePath;
        psi.Environment["PYTHONPATH"] = config.Paths.PackagePath;
        psi.Environment["AUTOMATION_INPUT_PATH"] = Path.Combine(config.Paths.InputPath, "input.json");
        psi.Environment["AUTOMATION_OUTPUT_PATH"] = config.Paths.OutputPath;
        return psi;
    }

    private static ProcessStartInfo BuildPythonModule(ExecutionConfig config)
    {
        var pythonExe = config.Entrypoint.ExecutablePath
            ?? Path.Combine(config.Paths.RuntimePath, "python.exe");

        var module = config.Entrypoint.Module
            ?? throw new InvalidOperationException("Python module entrypoint requires 'module'");

        var args = config.Entrypoint.Arguments ?? "";

        var psi = CreateBase(config, pythonExe, $"-u -m {module} {args}".Trim());
        psi.Environment["PYTHONPATH"] = config.Paths.PackagePath;
        psi.Environment["AUTOMATION_INPUT_PATH"] = Path.Combine(config.Paths.InputPath, "input.json");
        psi.Environment["AUTOMATION_OUTPUT_PATH"] = config.Paths.OutputPath;
        return psi;
    }

    private static ProcessStartInfo BuildPowerShell(ExecutionConfig config)
    {
        var pwsh = config.Entrypoint.ExecutablePath
            ?? ResolvePowerShellExecutable(config.Paths.RuntimePath);

        var script = config.Entrypoint.Script
            ?? throw new InvalidOperationException("PowerShell entrypoint requires 'script'");

        var scriptPath = Path.Combine(config.Paths.PackagePath, script);
        if (!File.Exists(scriptPath))
            throw new InvalidOperationException($"PowerShell script not found: {scriptPath}");

        return CreateBase(config, pwsh, $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"{scriptPath}\"");
    }

    // Bug real: o valor padrao antigo era sempre Path.Combine(RuntimePath,
    // "pwsh.exe") - ou seja, so funcionava se alguem baixasse e extraisse um
    // bundle de PowerShell 7 dentro do Runtime Store (nada faz isso hoje), e
    // quando RuntimePath vinha vazio (automacao powershell_script sem
    // runtime gerenciado - o caso comum) o Path.Combine virava so "pwsh.exe"
    // por acidente, dependendo de PowerShell 7 estar instalado e no PATH
    // sem nenhum fallback. PowerShell 7 (pwsh.exe) e um instalador a parte;
    // nem toda maquina Windows o tem. Agora: usa um pwsh.exe do runtime
    // gerenciado se realmente existir, senao procura no PATH, senao cai para
    // o Windows PowerShell 5.1 (powershell.exe) embutido em toda instalacao
    // do Windows - assim a automacao roda mesmo sem PowerShell 7 instalado.
    public static string ResolvePowerShellExecutable(string runtimePath)
    {
        if (!string.IsNullOrEmpty(runtimePath))
        {
            var bundled = Path.Combine(runtimePath, "pwsh.exe");
            if (File.Exists(bundled))
                return bundled;
        }

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

    private static ProcessStartInfo BuildExecutable(ExecutionConfig config)
    {
        var exePath = config.Entrypoint.ExecutablePath
            ?? throw new InvalidOperationException("Executable entrypoint requires 'executable_path'");

        var fullPath = Path.IsPathRooted(exePath) ? exePath : Path.Combine(config.Paths.PackagePath, exePath);
        if (!File.Exists(fullPath))
            throw new InvalidOperationException($"Executable not found: {fullPath}");

        // Validate the executable is within the package or runtime directories.
        // RuntimePath is empty for the "executable" entrypoint (it has no
        // managed runtime), so only check it when one is actually configured -
        // Path.GetFullPath("") throws ArgumentException("The path is empty").
        var normalExe = Path.GetFullPath(fullPath);
        var normalPkg = Path.GetFullPath(config.Paths.PackagePath);
        var withinPackage = normalExe.StartsWith(normalPkg, StringComparison.OrdinalIgnoreCase);
        var withinRuntime = !string.IsNullOrEmpty(config.Paths.RuntimePath)
            && normalExe.StartsWith(Path.GetFullPath(config.Paths.RuntimePath), StringComparison.OrdinalIgnoreCase);

        if (!withinPackage && !withinRuntime)
        {
            throw new InvalidOperationException("Executable must be within the package or runtime directory");
        }

        var args = config.Entrypoint.Arguments ?? "";
        return CreateBase(config, fullPath, args);
    }

    private static ProcessStartInfo BuildBrowserPlaywright(ExecutionConfig config)
    {
        var pythonExe = config.Entrypoint.ExecutablePath
            ?? Path.Combine(config.Paths.RuntimePath, "python.exe");

        var module = config.Entrypoint.Module ?? "automation.main";
        var callable = config.Entrypoint.Callable ?? "run";
        var args = config.Entrypoint.Arguments ?? "";

        var bootstrap = BuildPythonFunctionBootstrap(module, callable);
        var psi = CreateBase(config, pythonExe, $"-u -c \"{EncodeBootstrap(bootstrap)}\" {args}".Trim());
        psi.Environment["AUTOMATION_PACKAGE_PATH"] = config.Paths.PackagePath;
        psi.Environment["PYTHONPATH"] = config.Paths.PackagePath;
        psi.Environment["AUTOMATION_INPUT_PATH"] = Path.Combine(config.Paths.InputPath, "input.json");
        psi.Environment["AUTOMATION_OUTPUT_PATH"] = config.Paths.OutputPath;

        // Playwright isolation: separate browser data per execution
        var browserDataDir = Path.Combine(config.Paths.TempPath, "browser_data");
        Directory.CreateDirectory(browserDataDir);
        psi.Environment["PLAYWRIGHT_BROWSERS_PATH"] = Path.Combine(config.Paths.RuntimePath, "browsers");
        psi.Environment["PLAYWRIGHT_BROWSER_DATA"] = browserDataDir;

        return psi;
    }

    private static ProcessStartInfo BuildPythonDesktop(ExecutionConfig config)
    {
        if (!string.Equals(config.Mode, "interactive", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("python_desktop entrypoint is allowed only for interactive execution mode");

        var psi = config.Entrypoint.Module is null
            ? BuildPythonModule(config)
            : BuildPythonFunction(config);

        psi.Environment["AUTOMATION_INTERACTIVE_MODE"] = "true";
        psi.Environment["PYAUTOGUI_FAILSAFE"] = "true";
        psi.Environment["PYAUTOGUI_PAUSE_SECONDS"] = "0.1";

        if (config.InteractiveContext is not null)
        {
            psi.Environment["AUTOMATION_SESSION_ID"] = config.InteractiveContext.SessionId.ToString();
            psi.Environment["AUTOMATION_DESKTOP_DPI_SCALE"] = config.InteractiveContext.DpiScale?.ToString(System.Globalization.CultureInfo.InvariantCulture) ?? "";
            psi.Environment["AUTOMATION_MONITOR_COUNT"] = config.InteractiveContext.MonitorCount?.ToString() ?? "";
            if (config.InteractiveContext.DesktopResolution is not null)
            {
                psi.Environment["AUTOMATION_DESKTOP_WIDTH"] = config.InteractiveContext.DesktopResolution.Width.ToString();
                psi.Environment["AUTOMATION_DESKTOP_HEIGHT"] = config.InteractiveContext.DesktopResolution.Height.ToString();
            }
        }

        return psi;
    }

    private static string BuildPythonFunctionBootstrap(string module, string callable)
    {
        var moduleLiteral = JsonSerializer.Serialize(module);
        var callableLiteral = JsonSerializer.Serialize(callable);
        return $$"""
import importlib
import json
import os
import sys

package_path = os.environ.get("AUTOMATION_PACKAGE_PATH", "")
if package_path:
    sys.path.insert(0, package_path)

input_path = os.environ.get("AUTOMATION_INPUT_PATH", "")
if input_path and os.path.exists(input_path):
    with open(input_path, "r", encoding="utf-8") as handle:
        ctx = json.load(handle)
else:
    ctx = {}

target = importlib.import_module({{moduleLiteral}})
result = getattr(target, {{callableLiteral}})(ctx)
output_path = os.environ.get("AUTOMATION_OUTPUT_PATH", "")
if result is not None and output_path:
    os.makedirs(output_path, exist_ok=True)
    with open(os.path.join(output_path, "output.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, default=str)
""";
    }

    private static string EncodeBootstrap(string script)
    {
        var encoded = Convert.ToBase64String(Encoding.UTF8.GetBytes(script));
        return $"import base64; exec(base64.b64decode('{encoded}').decode('utf-8'))";
    }

    private static ProcessStartInfo CreateBase(ExecutionConfig config, string fileName, string arguments)
    {
        var psi = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = config.Paths.WorkspacePath,
            UseShellExecute = false,
            // Regressao: CreateNoWindow ficava hardcoded em "true" pra TODO
            // entrypoint (powershell_script, executable, python_function,
            // browser_playwright...), entao nao existia forma de pedir uma
            // automacao "visivel" - mesmo com uma automacao rodando em modo
            // interactive (o mesmo sinal que BuildPythonDesktop ja usa pra
            // saber se pode desenhar na tela com pyautogui), a janela do
            // processo filho (console do PowerShell, janela do .exe, etc.)
            // continuava sempre escondida. Agora: modo "interactive" mostra
            // a janela; qualquer outro modo (o padrao "background") continua
            // escondendo, como sempre foi - visivel ou nao vira uma escolha
            // real de quem publica a automacao (execution.mode no
            // manifesto), nao mais um valor fixo no codigo do Agent.
            CreateNoWindow = !string.Equals(config.Mode, "interactive", StringComparison.OrdinalIgnoreCase),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = false
        };

        // Set execution environment variables
        psi.Environment["AUTOMATION_EXECUTION_ID"] = config.ExecutionId;
        psi.Environment["AUTOMATION_ATTEMPT_ID"] = config.AttemptId;
        psi.Environment["AUTOMATION_WORKSPACE"] = config.Paths.WorkspacePath;
        psi.Environment["AUTOMATION_ARTIFACTS_PATH"] = config.Paths.ArtifactsPath;
        psi.Environment["AUTOMATION_TEMP_PATH"] = config.Paths.TempPath;
        psi.Environment["AUTOMATION_LOGS_PATH"] = config.Paths.LogsPath;
        psi.Environment["AUTOMATION_EXECUTION_MODE"] = config.Mode;

        // Apply custom environment (secrets via env vars, not command line)
        if (config.Environment is not null)
        {
            foreach (var (key, value) in config.Environment)
            {
                psi.Environment[key] = value;
            }
        }

        return psi;
    }
}
