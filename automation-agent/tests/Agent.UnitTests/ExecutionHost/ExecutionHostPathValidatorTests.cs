using Biason.AutomationAgent.ExecutionHost;
using Biason.AutomationAgent.ExecutionHost.Protocol;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.ExecutionHost;

public sealed class ExecutionHostPathValidatorTests : IDisposable
{
    private readonly string _workspacePath = Path.Combine(Path.GetTempPath(), $"ehpv_ws_{Guid.NewGuid():N}");

    // Regressao real, reproduzida rodando contra o Agent.Service online de
    // verdade (nao pegou em nenhum teste unitario anterior, porque
    // ExecutionManagerTests/RuntimeLauncherTests chamam ExecutionManager.
    // ExecuteAsync ou RuntimeLauncher.BuildStartInfo diretamente, pulando a
    // validacao que o ExecutionHost.exe roda sozinho no proprio Main): com
    // RuntimePath vazio (o caso esperado para powershell_script/executable
    // sem runtime gerenciado - ver ExecutionManager.RequiresManagedRuntime),
    // ExecutionHost morria com "Missing required path: RuntimePath" antes
    // de sequer chegar no RuntimeLauncher, que ja sabia lidar com isso.
    [Theory]
    [InlineData("powershell_script")]
    [InlineData("executable")]
    public void Validate_DoesNotRequireRuntimePath_ForLocallyInstalledEntrypoints(string entrypointType)
    {
        Directory.CreateDirectory(_workspacePath);
        var paths = BuildPaths(runtimePath: string.Empty);

        var act = () => ExecutionHostPathValidator.Validate(paths, entrypointType);

        act.Should().NotThrow();
    }

    // O oposto continua valendo: entrypoints que dependem de um runtime
    // gerenciado (ex.: python_function, que precisa do interpretador
    // baixado no Runtime Store) ainda devem falhar cedo e com uma mensagem
    // clara se RuntimePath vier vazio - essa validacao nao virou um bypass
    // geral.
    [Fact]
    public void Validate_StillRequiresRuntimePath_ForManagedRuntimeEntrypoints()
    {
        Directory.CreateDirectory(_workspacePath);
        var paths = BuildPaths(runtimePath: string.Empty);

        var act = () => ExecutionHostPathValidator.Validate(paths, "python_function");

        act.Should().Throw<InvalidOperationException>().WithMessage("Missing required path: RuntimePath");
    }

    private PathsConfig BuildPaths(string runtimePath) => new()
    {
        RuntimePath = runtimePath,
        PackagePath = _workspacePath,
        WorkspacePath = _workspacePath,
        InputPath = Path.Combine(_workspacePath, "input"),
        OutputPath = Path.Combine(_workspacePath, "output"),
        ArtifactsPath = Path.Combine(_workspacePath, "artifacts"),
        TempPath = Path.Combine(_workspacePath, "temp"),
        LogsPath = Path.Combine(_workspacePath, "logs")
    };

    public void Dispose()
    {
        try { Directory.Delete(_workspacePath, recursive: true); } catch { }
    }
}
