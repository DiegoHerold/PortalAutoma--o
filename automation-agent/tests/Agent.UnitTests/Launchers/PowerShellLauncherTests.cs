using Biason.AutomationAgent.Application.Launchers;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using FluentAssertions;
using Xunit;
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.UnitTests.Launchers;

public sealed class PowerShellLauncherTests
{
    [Fact]
    public void ResolvePowerShellExecutable_NeverThrows_AndReturnsAKnownCandidate()
    {
        // Regressao: antes desta correcao o launcher hardcodava "pwsh.exe"
        // (PowerShell 7, um instalador separado) e nao rodava nenhuma
        // automacao powershell_script em maquinas so com o Windows
        // PowerShell 5.1 embutido. Nao podemos garantir no CI qual esta
        // instalado, entao validamos so que a resolucao é uma das opcoes
        // validas e nunca lanca excecao.
        var resolved = PowerShellLauncher.ResolvePowerShellExecutable();

        resolved.Should().NotBeNullOrWhiteSpace();
        (resolved == "pwsh.exe"
            || resolved == "powershell.exe"
            || resolved.EndsWith("pwsh.exe", StringComparison.OrdinalIgnoreCase))
            .Should().BeTrue($"unexpected PowerShell executable resolution: {resolved}");
    }

    [Fact]
    public void BuildLaunchSpec_PointsAtTheResolvedPowerShellExecutable_AndQuotesTheScriptPath()
    {
        var launcher = new PowerShellLauncher();
        var packagePath = Path.Combine(Path.GetTempPath(), "pkg_powershell_test");
        var workspacePath = Path.Combine(Path.GetTempPath(), "ws_powershell_test");

        var manifest = new AutomationManifest
        {
            Id = "automation.demo_powershell",
            Name = "Demo PowerShell",
            Version = "1.0.0",
            Runtime = new ManifestRuntime { Id = "powershell", Version = "system" },
            Entrypoint = new ManifestEntrypoint { Type = EntrypointType.PowerShellScript, Script = "automation\\main.ps1" },
            Resources = new ManifestResources { Pool = PoolType.Background }
        };

        var context = new ExecutionContext
        {
            ExecutionId = "exe_1",
            AttemptId = "att_1",
            AutomationId = manifest.Id,
            AutomationVersionId = "package_1",
            Manifest = manifest,
            WorkspacePath = workspacePath,
            RuntimePath = string.Empty,
            PackagePath = packagePath,
            Pool = PoolType.Background,
            TimeoutSeconds = 60,
            GracefulShutdownSeconds = 5
        };

        var spec = launcher.BuildLaunchSpec(context);

        spec.ExecutablePath.Should().Be(PowerShellLauncher.ResolvePowerShellExecutable());
        spec.Arguments.Should().Contain(Path.Combine(packagePath, "automation\\main.ps1"));
        spec.Arguments.Should().StartWith("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File");
        spec.WorkingDirectory.Should().Be(workspacePath);
    }
}
