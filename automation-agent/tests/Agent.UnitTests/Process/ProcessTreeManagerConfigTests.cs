using System.Reflection;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Windows.Process;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using Xunit;
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

// Nao usar "Process" aqui: um namespace com esse ultimo segmento, aninhado
// direto sob Biason.AutomationAgent.UnitTests, colide com System.Diagnostics.Process
// (usado sem qualificar em ExecutionManagerTests.cs) - a busca de nomes do C#
// enxerga namespaces aninhados de QUALQUER arquivo do projeto a partir do
// namespace envolvente, sem precisar de "using", e isso quebrou o build com
// CS0118 ("Process" e um namespace, mas e usado como um tipo).
namespace Biason.AutomationAgent.UnitTests.ProcessTree;

public sealed class ProcessTreeManagerConfigTests : IDisposable
{
    private readonly string _workspacePath = Path.Combine(Path.GetTempPath(), $"ptm_config_{Guid.NewGuid():N}");

    // Regressao: WriteConfigFileAsync serializava "executable_path" como
    // null incondicionalmente, entao TODA automacao do tipo "executable"
    // chegava no ExecutionHost sem o caminho do .exe e falhava sempre com
    // "Executable entrypoint requires 'executable_path'"
    // (RuntimeLauncher.BuildExecutable), mesmo com manifest.Entrypoint.Path
    // corretamente preenchido. Testamos direto o metodo privado que grava o
    // config (via reflection) para nao depender de Job Objects nativos do
    // Windows/lancar um ExecutionHost.exe real so para verificar o JSON.
    [Fact]
    public async Task WriteConfigFileAsync_PropagatesEntrypointPath_ForExecutableType()
    {
        Directory.CreateDirectory(_workspacePath);

        var dirs = Substitute.For<IDirectoryResolver>();
        var manager = new ProcessTreeManager(
            new JobObjectManager(NullLogger<JobObjectManager>.Instance),
            dirs,
            NullLogger<ProcessTreeManager>.Instance);

        var manifest = new AutomationManifest
        {
            Id = "automation.demo_executable",
            Name = "Demo Executable",
            Version = "1.0.0",
            Runtime = new ManifestRuntime { Id = "executable", Version = "1.0" },
            Entrypoint = new ManifestEntrypoint
            {
                Type = EntrypointType.Executable,
                Path = "automation\\ExampleTool.exe"
            },
            Resources = new ManifestResources { Pool = PoolType.Background }
        };

        var context = new ExecutionContext
        {
            ExecutionId = "exe_1",
            AttemptId = "att_1",
            AutomationId = manifest.Id,
            AutomationVersionId = "package_1",
            Manifest = manifest,
            WorkspacePath = _workspacePath,
            RuntimePath = string.Empty,
            PackagePath = Path.Combine(_workspacePath, "package"),
            Pool = PoolType.Background,
            TimeoutSeconds = 60,
            GracefulShutdownSeconds = 5
        };

        var method = typeof(ProcessTreeManager).GetMethod("WriteConfigFileAsync", BindingFlags.NonPublic | BindingFlags.Instance)
            ?? throw new InvalidOperationException("WriteConfigFileAsync not found - did the method get renamed?");

        var task = (Task<string>)method.Invoke(manager, new object[] { context, "pipe_test", CancellationToken.None })!;
        var configPath = await task;

        var json = await File.ReadAllTextAsync(configPath);
        using var doc = JsonDocument.Parse(json);
        var entrypoint = doc.RootElement.GetProperty("entrypoint");

        entrypoint.GetProperty("executable_path").GetString().Should().Be("automation\\ExampleTool.exe");
    }

    // Regressao real, achada rodando contra o Agent.Service online (nenhum
    // teste unitario cobria isso antes): ResolveExecutionHostPath escolhia o
    // primeiro candidato da lista que existisse - e a lista colocava
    // bin/Debug antes de bin/Release. Um ExecutionHost.exe de Debug de dias
    // atras, deixado no disco por um build anterior, sempre vencia o
    // bin/Release recem-compilado, entao a correcao de codigo nunca chegava
    // a rodar de verdade, nao importava quantas vezes a solution fosse
    // recompilada em Release. Testamos direto o metodo privado que escolhe
    // entre os candidatos (via reflection) com arquivos temporarios reais,
    // sem depender de AppContext.BaseDirectory nem da estrutura bin/ do repo.
    [Fact]
    public void PickNewestExisting_PrefersMostRecentlyWrittenFile_RegardlessOfListOrder()
    {
        var older = Path.Combine(_workspacePath, "old_debug", "ExecutionHost.exe");
        var newer = Path.Combine(_workspacePath, "new_release", "ExecutionHost.exe");
        Directory.CreateDirectory(Path.GetDirectoryName(older)!);
        Directory.CreateDirectory(Path.GetDirectoryName(newer)!);
        File.WriteAllText(older, "old");
        File.WriteAllText(newer, "new");
        File.SetLastWriteTimeUtc(older, DateTime.UtcNow.AddDays(-6));
        File.SetLastWriteTimeUtc(newer, DateTime.UtcNow);

        var missing = Path.Combine(_workspacePath, "does_not_exist", "ExecutionHost.exe");

        var method = typeof(ProcessTreeManager).GetMethod("PickNewestExisting", BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException("PickNewestExisting not found - did the method get renamed?");

        // Ordem deliberadamente igual ao bug real: o candidato ANTIGO (Debug)
        // vem ANTES do candidato NOVO (Release) na lista.
        var candidates = new[] { missing, older, newer };
        var result = (string?)method.Invoke(null, new object[] { candidates });

        result.Should().Be(newer);
    }

    [Fact]
    public void PickNewestExisting_ReturnsNull_WhenNoCandidateExists()
    {
        var method = typeof(ProcessTreeManager).GetMethod("PickNewestExisting", BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException("PickNewestExisting not found - did the method get renamed?");

        var candidates = new[] { Path.Combine(_workspacePath, "nope", "ExecutionHost.exe") };
        var result = (string?)method.Invoke(null, new object[] { candidates });

        result.Should().BeNull();
    }

    public void Dispose()
    {
        try { Directory.Delete(_workspacePath, recursive: true); } catch { }
    }
}
