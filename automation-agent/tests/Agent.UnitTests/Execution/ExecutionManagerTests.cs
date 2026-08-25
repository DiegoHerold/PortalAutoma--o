using System.Diagnostics;
using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.UnitTests.Execution;

public sealed class ExecutionManagerTests : IDisposable
{
    private readonly string _workspacePath = Path.Combine(Path.GetTempPath(), $"exec_mgr_{Guid.NewGuid():N}");

    [Fact]
    public async Task ExecuteAsync_UsesCurrentAttemptIdFromPortalCommit()
    {
        var officialAttemptId = "att_portal_123";
        var execution = new ExecutionRecord
        {
            ExecutionId = "exe_portal_123",
            AutomationId = "automation.echo",
            AutomationVersionId = "package_1",
            CurrentAttemptId = officialAttemptId,
            CurrentState = ExecutionState.Committed,
            CreatedAtUtc = DateTime.UtcNow,
            LastTransitionUtc = DateTime.UtcNow
        };

        var execRepo = Substitute.For<IExecutionRepository>();
        var attemptRepo = Substitute.For<IExecutionAttemptRepository>();
        var capacity = Substitute.For<ICapacityManager>();
        var reservations = Substitute.For<IResourceReservationManager>();
        var workspace = Substitute.For<IWorkspaceManager>();
        var processManager = Substitute.For<IProcessManager>();
        var cancellation = Substitute.For<ICancellationManager>();
        var results = Substitute.For<IResultCollector>();
        var runtimeStore = Substitute.For<IRuntimeStore>();
        var packageStore = Substitute.For<IPackageStore>();
        var clock = Substitute.For<IClock>();

        var now = new DateTime(2026, 8, 14, 12, 0, 0, DateTimeKind.Utc);
        clock.UtcNow.Returns(now);
        Directory.CreateDirectory(Path.Combine(_workspacePath, "input"));
        Directory.CreateDirectory(Path.Combine(_workspacePath, "output"));
        Directory.CreateDirectory(Path.Combine(_workspacePath, "logs"));
        workspace.CreateWorkspace(execution.ExecutionId, officialAttemptId).Returns(_workspacePath);
        runtimeStore.GetPath("python-core", "3.13").Returns(_workspacePath);
        packageStore.GetPath("package_1").Returns(_workspacePath);
        cancellation.CreateLinked(execution.ExecutionId, Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(_ => new CancellationTokenSource());
        results.CollectAsync(execution.ExecutionId, officialAttemptId, _workspacePath, 0, Arg.Any<CancellationToken>())
            .Returns(new ExecutionResult
            {
                ExecutionId = execution.ExecutionId,
                AttemptId = officialAttemptId,
                Success = true,
                ExitCode = 0,
                CompletedAtUtc = now
            });

        ExecutionContext? launchedContext = null;
        processManager.LaunchAsync(Arg.Do<ExecutionContext>(ctx => launchedContext = ctx), Arg.Any<CancellationToken>())
            .Returns(_ =>
            {
                var process = StartAlreadySuccessfulProcess();
                return Task.FromResult(new ProcessHandle
                {
                    ProcessId = process.Id,
                    PipeName = "unit-test",
                    Process = process
                });
            });

        var sut = new ExecutionManager(
            execRepo,
            attemptRepo,
            Substitute.For<IAdmissionController>(),
            capacity,
            reservations,
            workspace,
            processManager,
            cancellation,
            results,
            runtimeStore,
            packageStore,
            Array.Empty<ILauncher>(),
            clock,
            Options.Create(new ExecutionOptions()),
            NullLogger<ExecutionManager>.Instance);

        var manifest = new AutomationManifest
        {
            Id = "automation.echo",
            Name = "Automation Echo",
            Version = "1.0.0",
            Runtime = new ManifestRuntime { Id = "python-core", Version = "3.13" },
            Entrypoint = new ManifestEntrypoint { Type = EntrypointType.PythonFunction },
            Resources = new ManifestResources { Pool = PoolType.Background }
        };

        var result = await sut.ExecuteAsync(execution, manifest, """{"message":"hello"}""");

        result.AttemptId.Should().Be(officialAttemptId);
        launchedContext.Should().NotBeNull();
        launchedContext!.AttemptId.Should().Be(officialAttemptId);
        await attemptRepo.Received().SaveAsync(Arg.Is<ExecutionAttempt>(a => a.AttemptId == officialAttemptId), Arg.Any<CancellationToken>());
        workspace.Received(1).CreateWorkspace(execution.ExecutionId, officialAttemptId);
    }

    [Theory]
    [InlineData(EntrypointType.PowerShellScript)]
    [InlineData(EntrypointType.Executable)]
    public async Task ExecuteAsync_DoesNotRequireRuntimeStoreEntry_ForLocallyInstalledEntrypoints(EntrypointType entrypointType)
    {
        // PowerShellScript e Executable rodam contra binarios ja instalados
        // na maquina (pwsh.exe do PATH, ou o .exe empacotado no pacote) - os
        // launchers reais nunca leem ExecutionContext.RuntimePath para esses
        // tipos, entao a execucao nao deve exigir uma entrada no Runtime
        // Store so porque o manifest declara um runtime.id.
        var execution = new ExecutionRecord
        {
            ExecutionId = $"exe_{entrypointType}_test",
            AutomationId = "automation.local_binary",
            AutomationVersionId = "package_1",
            CurrentAttemptId = "att_local_binary",
            CurrentState = ExecutionState.Committed,
            CreatedAtUtc = DateTime.UtcNow,
            LastTransitionUtc = DateTime.UtcNow
        };

        var execRepo = Substitute.For<IExecutionRepository>();
        var attemptRepo = Substitute.For<IExecutionAttemptRepository>();
        var capacity = Substitute.For<ICapacityManager>();
        var reservations = Substitute.For<IResourceReservationManager>();
        var workspace = Substitute.For<IWorkspaceManager>();
        var processManager = Substitute.For<IProcessManager>();
        var cancellation = Substitute.For<ICancellationManager>();
        var results = Substitute.For<IResultCollector>();
        var runtimeStore = Substitute.For<IRuntimeStore>();
        var packageStore = Substitute.For<IPackageStore>();
        var clock = Substitute.For<IClock>();

        var now = new DateTime(2026, 8, 20, 12, 0, 0, DateTimeKind.Utc);
        clock.UtcNow.Returns(now);
        Directory.CreateDirectory(Path.Combine(_workspacePath, "input"));
        Directory.CreateDirectory(Path.Combine(_workspacePath, "output"));
        Directory.CreateDirectory(Path.Combine(_workspacePath, "logs"));
        workspace.CreateWorkspace(execution.ExecutionId, "att_local_binary").Returns(_workspacePath);

        // Nenhum diretorio de runtime store cadastrado - GetPath retorna null
        // (comportamento padrao do NSubstitute), simulando o caso real de
        // automacoes powershell_script/executable, que nunca tem um runtime
        // baixado/extraido pelo Agent.
        packageStore.GetPath("package_1").Returns(_workspacePath);
        cancellation.CreateLinked(execution.ExecutionId, Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(_ => new CancellationTokenSource());
        results.CollectAsync(execution.ExecutionId, "att_local_binary", _workspacePath, 0, Arg.Any<CancellationToken>())
            .Returns(new ExecutionResult
            {
                ExecutionId = execution.ExecutionId,
                AttemptId = "att_local_binary",
                Success = true,
                ExitCode = 0,
                CompletedAtUtc = now
            });

        processManager.LaunchAsync(Arg.Any<ExecutionContext>(), Arg.Any<CancellationToken>())
            .Returns(_ =>
            {
                var process = StartAlreadySuccessfulProcess();
                return Task.FromResult(new ProcessHandle
                {
                    ProcessId = process.Id,
                    PipeName = "unit-test",
                    Process = process
                });
            });

        var sut = new ExecutionManager(
            execRepo,
            attemptRepo,
            Substitute.For<IAdmissionController>(),
            capacity,
            reservations,
            workspace,
            processManager,
            cancellation,
            results,
            runtimeStore,
            packageStore,
            Array.Empty<ILauncher>(),
            clock,
            Options.Create(new ExecutionOptions()),
            NullLogger<ExecutionManager>.Instance);

        var manifest = new AutomationManifest
        {
            Id = "automation.local_binary",
            Name = "Automation Local Binary",
            Version = "1.0.0",
            Runtime = new ManifestRuntime { Id = "powershell", Version = "system" },
            Entrypoint = new ManifestEntrypoint { Type = entrypointType },
            Resources = new ManifestResources { Pool = PoolType.Background }
        };

        var result = await sut.ExecuteAsync(execution, manifest, """{"message":"hello"}""");

        result.Success.Should().BeTrue();
        result.ErrorOutput.Should().NotBe($"Runtime not found: powershell:system");
    }

    private static Process StartAlreadySuccessfulProcess()
    {
        var psi = OperatingSystem.IsWindows()
            ? new ProcessStartInfo("cmd.exe", "/c exit 0")
            : new ProcessStartInfo("/bin/sh", "-c \"exit 0\"");

        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        return Process.Start(psi) ?? throw new InvalidOperationException("Could not start test process.");
    }

    public void Dispose()
    {
        try { Directory.Delete(_workspacePath, recursive: true); } catch { }
    }
}
