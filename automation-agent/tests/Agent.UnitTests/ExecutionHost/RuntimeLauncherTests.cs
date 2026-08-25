using Biason.AutomationAgent.ExecutionHost.Launchers;
using Biason.AutomationAgent.ExecutionHost.Protocol;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.ExecutionHost;

public sealed class RuntimeLauncherTests : IDisposable
{
    private readonly string _packagePath = Path.Combine(Path.GetTempPath(), $"rl_pkg_{Guid.NewGuid():N}");

    // Regressao: o valor padrao antigo para pwsh era sempre
    // Path.Combine(RuntimePath, "pwsh.exe") - quando RuntimePath vinha vazio
    // (caso comum de powershell_script sem runtime gerenciado), isso virava
    // por acidente so "pwsh.exe" (dependente de PowerShell 7 estar
    // instalado), sem nenhum fallback para o Windows PowerShell 5.1
    // embutido em toda instalacao do Windows.
    [Fact]
    public void BuildPowerShell_DoesNotRequireRuntimePath_AndResolvesToAKnownExecutable()
    {
        Directory.CreateDirectory(_packagePath);
        Directory.CreateDirectory(Path.Combine(_packagePath, "automation"));
        var scriptPath = Path.Combine(_packagePath, "automation", "main.ps1");
        File.WriteAllText(scriptPath, "Write-Output 'ok'");

        var config = new ExecutionConfig
        {
            ExecutionId = "exe_ps_1",
            AttemptId = "att_ps_1",
            AutomationId = "automation.demo_powershell",
            Entrypoint = new EntrypointConfig
            {
                Type = "powershell_script",
                Script = "automation\\main.ps1"
            },
            Paths = new PathsConfig
            {
                RuntimePath = string.Empty, // nenhum runtime gerenciado - o caso real
                PackagePath = _packagePath,
                WorkspacePath = _packagePath,
                InputPath = Path.Combine(_packagePath, "input"),
                OutputPath = Path.Combine(_packagePath, "output"),
                ArtifactsPath = Path.Combine(_packagePath, "artifacts"),
                TempPath = Path.Combine(_packagePath, "temp"),
                LogsPath = Path.Combine(_packagePath, "logs")
            }
        };

        var startInfo = RuntimeLauncher.BuildStartInfo(config);

        startInfo.FileName.Should().Be(RuntimeLauncher.ResolvePowerShellExecutable(string.Empty));
        (startInfo.FileName == "pwsh.exe"
            || startInfo.FileName == "powershell.exe"
            || startInfo.FileName.EndsWith("pwsh.exe", StringComparison.OrdinalIgnoreCase))
            .Should().BeTrue($"unexpected PowerShell executable resolution: {startInfo.FileName}");
        startInfo.Arguments.Should().Contain(scriptPath);
    }

    public void Dispose()
    {
        try { Directory.Delete(_packagePath, recursive: true); } catch { }
    }

    [Fact]
    public void PythonFunctionBootstrap_IsEncodedAndUsesPackageEnvironment()
    {
        var config = new ExecutionConfig
        {
            ExecutionId = "exe_1",
            AttemptId = "att_1",
            AutomationId = "automation.echo",
            Entrypoint = new EntrypointConfig
            {
                Type = "python_function",
                Module = "automation.main",
                Callable = "run"
            },
            Paths = new PathsConfig
            {
                RuntimePath = @"C:\runtime",
                PackagePath = @"C:\packages\echo",
                WorkspacePath = @"C:\workspace",
                InputPath = @"C:\workspace\input",
                OutputPath = @"C:\workspace\output",
                ArtifactsPath = @"C:\workspace\artifacts",
                TempPath = @"C:\workspace\temp",
                LogsPath = @"C:\workspace\logs"
            }
        };

        var startInfo = RuntimeLauncher.BuildStartInfo(config);

        startInfo.Arguments.Should().Contain("base64.b64decode");
        startInfo.Arguments.Should().NotContain("; if result is not None");
        startInfo.Environment["AUTOMATION_PACKAGE_PATH"].Should().Be(config.Paths.PackagePath);
    }

    // Regressao: CreateNoWindow ficava fixo em "true" pra qualquer automacao,
    // entao nao existia como pedir uma automacao "visivel" (janela do
    // PowerShell/executavel aparecendo na tela) - nem executando em modo
    // interactive. Corrigido: CreateNoWindow agora acompanha config.Mode, o
    // mesmo sinal que BuildPythonDesktop ja usa pra saber se pode atuar num
    // desktop real.
    [Theory]
    [InlineData("background", true)]
    [InlineData(null, true)] // "background" e o default de ExecutionConfig.Mode
    [InlineData("interactive", false)]
    [InlineData("INTERACTIVE", false)] // comparacao deve ignorar maiusculas/minusculas
    public void BuildPowerShell_WindowVisibility_FollowsExecutionMode(string? mode, bool expectedCreateNoWindow)
    {
        Directory.CreateDirectory(_packagePath);
        Directory.CreateDirectory(Path.Combine(_packagePath, "automation"));
        var scriptPath = Path.Combine(_packagePath, "automation", "main.ps1");
        File.WriteAllText(scriptPath, "Write-Output 'ok'");

        var config = new ExecutionConfig
        {
            ExecutionId = "exe_ps_vis",
            AttemptId = "att_ps_vis",
            AutomationId = "automation.demo_powershell",
            Mode = mode ?? "background",
            Entrypoint = new EntrypointConfig
            {
                Type = "powershell_script",
                Script = "automation\\main.ps1"
            },
            Paths = new PathsConfig
            {
                RuntimePath = string.Empty,
                PackagePath = _packagePath,
                WorkspacePath = _packagePath,
                InputPath = Path.Combine(_packagePath, "input"),
                OutputPath = Path.Combine(_packagePath, "output"),
                ArtifactsPath = Path.Combine(_packagePath, "artifacts"),
                TempPath = Path.Combine(_packagePath, "temp"),
                LogsPath = Path.Combine(_packagePath, "logs")
            }
        };

        var startInfo = RuntimeLauncher.BuildStartInfo(config);

        startInfo.CreateNoWindow.Should().Be(expectedCreateNoWindow);
    }
}
