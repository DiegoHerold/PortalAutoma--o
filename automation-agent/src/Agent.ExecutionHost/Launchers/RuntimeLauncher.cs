using System.Diagnostics;
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

        // Bootstrap script that calls the function with proper context
        var bootstrap = string.Join("; ", new[]
        {
            "import sys",
            "import json",
            "import os",
            $"sys.path.insert(0, r'{config.Paths.PackagePath}')",
            $"import {module}",
            "input_path = os.environ.get('AUTOMATION_INPUT_PATH', '')",
            "ctx = json.load(open(input_path)) if input_path and os.path.exists(input_path) else {}",
            $"result = {module}.{callable}(ctx)",
            "output_path = os.environ.get('AUTOMATION_OUTPUT_PATH', '')",
            "if result is not None and output_path: json.dump(result, open(os.path.join(output_path, 'output.json'), 'w'), default=str)"
        });

        var psi = CreateBase(config, pythonExe, $"-u -c \"{bootstrap}\"");
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
            ?? Path.Combine(config.Paths.RuntimePath, "pwsh.exe");

        var script = config.Entrypoint.Script
            ?? throw new InvalidOperationException("PowerShell entrypoint requires 'script'");

        var scriptPath = Path.Combine(config.Paths.PackagePath, script);
        if (!File.Exists(scriptPath))
            throw new InvalidOperationException($"PowerShell script not found: {scriptPath}");

        return CreateBase(config, pwsh, $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"{scriptPath}\"");
    }

    private static ProcessStartInfo BuildExecutable(ExecutionConfig config)
    {
        var exePath = config.Entrypoint.ExecutablePath
            ?? throw new InvalidOperationException("Executable entrypoint requires 'executable_path'");

        var fullPath = Path.IsPathRooted(exePath) ? exePath : Path.Combine(config.Paths.PackagePath, exePath);
        if (!File.Exists(fullPath))
            throw new InvalidOperationException($"Executable not found: {fullPath}");

        // Validate the executable is within the package or runtime directories
        var normalExe = Path.GetFullPath(fullPath);
        var normalPkg = Path.GetFullPath(config.Paths.PackagePath);
        var normalRt = Path.GetFullPath(config.Paths.RuntimePath);

        if (!normalExe.StartsWith(normalPkg, StringComparison.OrdinalIgnoreCase)
            && !normalExe.StartsWith(normalRt, StringComparison.OrdinalIgnoreCase))
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

        var bootstrap = string.Join("; ", new[]
        {
            "import sys",
            "import json",
            "import os",
            $"sys.path.insert(0, r'{config.Paths.PackagePath}')",
            $"import {module}",
            "input_path = os.environ.get('AUTOMATION_INPUT_PATH', '')",
            "ctx = json.load(open(input_path)) if input_path and os.path.exists(input_path) else {}",
            $"result = {module}.{callable}(ctx)",
            "output_path = os.environ.get('AUTOMATION_OUTPUT_PATH', '')",
            "if result is not None and output_path: json.dump(result, open(os.path.join(output_path, 'output.json'), 'w'), default=str)"
        });

        var psi = CreateBase(config, pythonExe, $"-u -c \"{bootstrap}\" {args}".Trim());
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

    private static ProcessStartInfo CreateBase(ExecutionConfig config, string fileName, string arguments)
    {
        var psi = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = config.Paths.WorkspacePath,
            UseShellExecute = false,
            CreateNoWindow = true,
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
