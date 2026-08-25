using System.Text.Json;
using Biason.AutomationAgent.Certification.Core;
using Biason.AutomationAgent.Certification.Core.Diagnostics;
using Biason.AutomationAgent.Certification.Core.Portal;
using Biason.AutomationAgent.Certification.Core.Processes;
using Biason.AutomationAgent.Certification.Core.Reporting;
using Biason.AutomationAgent.Certification.Core.RuntimeProvisioning;
using Biason.AutomationAgent.Certification.Cli;
using Microsoft.Extensions.Logging;

var loggerFactory = LoggerFactory.Create(builder => builder
    .AddSimpleConsole(o => { o.SingleLine = true; o.TimestampFormat = "HH:mm:ss "; })
    .SetMinimumLevel(LogLevel.Information));
var logger = loggerFactory.CreateLogger("certification");

var command = args.Length > 0 ? args[0] : "help";
var rest = args.Skip(1).ToArray();

try
{
    return command switch
    {
        "prepare" => await Commands.PrepareAsync(loggerFactory, logger),
        "start" => await Commands.StartAsync(loggerFactory, logger),
        "status" => await Commands.StatusAsync(loggerFactory, logger),
        "run" => await Commands.RunAsync(loggerFactory, logger, rest),
        "stop" => await Commands.StopAsync(loggerFactory, logger),
        "clean" => await Commands.CleanAsync(loggerFactory, logger, rest),
        _ => Commands.PrintUsage()
    };
}
catch (Exception ex)
{
    logger.LogError(ex, "certification {Command} failed.", command);
    return 1;
}

namespace Biason.AutomationAgent.Certification.Cli
{
    internal static class Commands
    {
        private const string AgentDisplayName = "certification-agent-01";
        private const string PidFileName = "agent-service";

        internal static int PrintUsage()
        {
            Console.WriteLine("""
                Usage: certification <command>

                Commands:
                  prepare   Start/reuse Portal (docker compose), seed certification
                            automations/packages, ensure the certification runtime is
                            available.
                  start     Launch Agent.Service under the isolated certification
                            profile and wait for it to register and come online.
                  status    Print current Portal/Gateway/Agent readiness without
                            starting anything.
                  run <scenario|all>
                            Create and observe certification executions
                            (echo|fail|timeout|cancel|progress|artifact|background|all) and write
                            certification-runs/<run_id>/report.json.
                  stop      Gracefully stop the supervised Agent.Service.
                  clean     Remove temporary certification data. See --help output
                            in docs/certification-harness.md for flags.
                """);
            return 0;
        }

        private static (CertificationOptions options, string repoRoot) Setup()
        {
            var repoRoot = RepoLocator.Resolve();
            var options = CertificationOptions.FromEnvironment(repoRoot);
            return (options, repoRoot);
        }

        // -- prepare -----------------------------------------------------

        internal static async Task<int> PrepareAsync(ILoggerFactory loggerFactory, ILogger logger)
        {
            var (options, repoRoot) = Setup();
            var compose = new ComposeOrchestrator(repoRoot);

            logger.LogInformation("Checking Docker Compose stack...");
            if (!await compose.IsStackRunningAsync())
            {
                logger.LogInformation("Stack not fully healthy yet; running 'docker compose up -d'.");
                await compose.UpAsync();
            }
            else
            {
                logger.LogInformation("Stack already running; reusing it (docs item 16).");
            }

            using var http = new HttpClient { BaseAddress = new Uri(options.PortalApiBaseUrl), Timeout = TimeSpan.FromSeconds(10) };
            var health = new PortalHealth(http);

            var portalReady = await PortalHealth.WaitUntilAsync(
                health.CheckPortalHealthAsync, TimeSpan.FromSeconds(options.PortalStartupTimeoutSeconds), TimeSpan.FromSeconds(2));
            logger.LogInformation("Portal health: {Status}", portalReady ? "READY" : "NOT READY");

            var gatewayReady = await PortalHealth.WaitUntilAsync(
                health.CheckGatewayHealthAsync, TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(2));
            logger.LogInformation("Gateway health: {Status}", gatewayReady ? "READY" : "NOT READY");

            var storageStates = await compose.PsAsync();
            var storageReady = storageStates.TryGetValue("minio", out var minioState) &&
                (minioState is "healthy" or "running");
            logger.LogInformation("Storage (MinIO) health: {Status}", storageReady ? "READY" : "NOT READY");

            if (!portalReady || !storageReady)
            {
                logger.LogError("BLOCKED: Portal or Storage not ready — refusing to seed or continue (item 52).");
                return 3;
            }

            logger.LogInformation("Seeding certification automations/versions/packages via the Portal API...");
            var backendCli = new BackendCli(repoRoot);
            var seedResult = await backendCli.SeedAsync();
            foreach (var property in seedResult.RootElement.EnumerateObject())
            {
                logger.LogInformation("  {Package}: automation_version_id={VersionId} status={Status}",
                    property.Name,
                    property.Value.GetProperty("automation_version_id"),
                    property.Value.GetProperty("status").GetString());
            }

            logger.LogInformation("Checking certification runtime (python-core/3.13)...");
            var runtimeAvailable = RuntimeSeeder.IsRuntimeAvailable(
                options.DataDirectory, "python-core", "3.13", loggerFactory);

            if (!runtimeAvailable)
            {
                var archiveEnv = Environment.GetEnvironmentVariable("CERTIFICATION_RUNTIME_ARCHIVE");
                if (!string.IsNullOrEmpty(archiveEnv) && File.Exists(archiveEnv))
                {
                    logger.LogInformation("Importing runtime archive {Archive} into the certification Runtime Store...", archiveEnv);
                    await RuntimeSeeder.ImportRuntimeAsync(options.DataDirectory, "python-core", "3.13", archiveEnv, loggerFactory);
                    runtimeAvailable = true;
                }
                else
                {
                    logger.LogWarning(
                        "Runtime NOT available and CERTIFICATION_RUNTIME_ARCHIVE is not set. " +
                        "Provide a real Python 3.13 embeddable distribution zip for win-x64 and re-run " +
                        "'certification prepare' with CERTIFICATION_RUNTIME_ARCHIVE=<path>. " +
                        "See docs/certification-harness.md, 'Runtime de certificação'.");
                }
            }
            logger.LogInformation("Runtime: {Status}", runtimeAvailable ? "READY" : "NOT READY (see warning above)");

            logger.LogInformation("prepare finished. Portal={Portal} Gateway={Gateway} Storage={Storage} Runtime={Runtime}",
                portalReady, gatewayReady, storageReady, runtimeAvailable);
            return portalReady && gatewayReady && storageReady && runtimeAvailable ? 0 : 3;
        }

        // -- start ---------------------------------------------------------

        internal static async Task<int> StartAsync(ILoggerFactory loggerFactory, ILogger logger)
        {
            var (options, repoRoot) = Setup();
            var supervisor = new CertificationProcessSupervisor(loggerFactory.CreateLogger<CertificationProcessSupervisor>());
            var paths = new CertificationPaths(repoRoot, "current");
            paths.EnsureDirectoriesExist();

            var pidFile = Path.Combine(paths.PidDirectory, $"{PidFileName}.pid");
            if (supervisor.RecoverStalePidFile(pidFile))
                logger.LogWarning("Recovered a stale Agent.Service process from a previous run (item 58).");

            using var http = new HttpClient { BaseAddress = new Uri(options.PortalApiBaseUrl), Timeout = TimeSpan.FromSeconds(10) };
            var admin = new PortalAdminClient(http);
            await admin.LoginAsync(options.AdminEmail, options.AdminPassword);

            logger.LogInformation("Requesting a fresh Agent registration token...");
            var registrationToken = await admin.CreateRegistrationTokenAsync(3600);

            Directory.CreateDirectory(options.DataDirectory);

            var environment = new Dictionary<string, string?>
            {
                ["DOTNET_ENVIRONMENT"] = "Certification",
                ["AUTOMATION_AGENT_DATA_DIR"] = options.DataDirectory,
                ["AUTOMATION_AGENT_Portal__Enabled"] = "true",
                ["AUTOMATION_AGENT_Portal__ApiBaseUrl"] = options.PortalApiBaseUrl,
                ["AUTOMATION_AGENT_Portal__WebSocketUrl"] = options.PortalWebSocketUrl,
                ["AUTOMATION_AGENT_Portal__RegistrationToken"] = registrationToken,
                ["AUTOMATION_AGENT_Agent__Name"] = options.AgentDisplayName,
            };

            var (fileName, arguments, workingDirectory) = options.AgentServiceIsProject
                ? ("dotnet", $"run --project \"{options.AgentServiceEntryPath}\" --no-launch-profile", Path.GetDirectoryName(options.AgentServiceEntryPath) ?? repoRoot)
                : (options.AgentServiceEntryPath, "", Path.GetDirectoryName(options.AgentServiceEntryPath) ?? repoRoot);

            logger.LogInformation("Starting Agent.Service (isolated data dir: {DataDir})...", options.DataDirectory);
            var handle = supervisor.Start(
                PidFileName, fileName, arguments, workingDirectory, environment, paths.AgentLogsPath, paths.PidDirectory);

            logger.LogInformation("Waiting for Agent registration/online/heartbeat (timeout {Timeout}s)...",
                options.AgentStartupTimeoutSeconds);

            var deadline = DateTimeOffset.UtcNow.AddSeconds(options.AgentStartupTimeoutSeconds);
            AgentReadiness readiness = new(AgentReadinessState.NotRegistered, null, null, null, null, false);
            while (DateTimeOffset.UtcNow < deadline)
            {
                if (!supervisor.IsRunning(handle))
                {
                    logger.LogError("Agent.Service process exited before becoming ready (PID {Pid}). Exit code: {ExitCode}",
                        handle.ProcessId, TryReadExitCode(handle));
                    await WriteDiagnosticsAsync(loggerFactory, options, http, handle, null, paths);
                    return 3;
                }

                var agentJson = await admin.FindAgentByNameAsync(options.AgentDisplayName);
                readiness = AgentReadinessEvaluator.Evaluate(agentJson, TimeSpan.FromSeconds(60), DateTimeOffset.UtcNow);
                if (readiness.IsReady)
                    break;

                await Task.Delay(TimeSpan.FromSeconds(2));
            }

            if (!readiness.IsReady)
            {
                logger.LogError("Agent did not reach READY/DEGRADED within {Timeout}s (last state: {State}).",
                    options.AgentStartupTimeoutSeconds, readiness.State);
                var dumpPath = await WriteDiagnosticsAsync(loggerFactory, options, http, handle, readiness, paths);
                logger.LogError("Diagnostic dump written to {Path}", dumpPath);
                return 3;
            }

            logger.LogInformation(
                "Agent READY. agent_id={AgentId} connectivity={Connectivity} health={Health} last_seen={LastSeen}",
                readiness.AgentId, readiness.ConnectivityStatus, readiness.HealthStatus, readiness.LastSeenAtUtc);
            return 0;
        }

        private static async Task<string> WriteDiagnosticsAsync(
            ILoggerFactory loggerFactory,
            CertificationOptions options,
            HttpClient http,
            ManagedProcessHandle? handle,
            AgentReadiness? readiness,
            CertificationPaths paths)
        {
            var health = new PortalHealth(http);
            var portalProbe = await health.CheckPortalHealthAsync();
            var gatewayProbe = await health.CheckGatewayHealthAsync();
            return await DiagnosticDump.WriteAsync(paths.AgentLogsPath, portalProbe, gatewayProbe, readiness, handle);
        }

        private static int? TryReadExitCode(ManagedProcessHandle handle)
        {
            try
            {
                using var process = System.Diagnostics.Process.GetProcessById(handle.ProcessId);
                return process.HasExited ? process.ExitCode : null;
            }
            catch
            {
                return null;
            }
        }

        // -- status ------------------------------------------------------

        internal static async Task<int> StatusAsync(ILoggerFactory loggerFactory, ILogger logger)
        {
            var (options, repoRoot) = Setup();
            using var http = new HttpClient { BaseAddress = new Uri(options.PortalApiBaseUrl), Timeout = TimeSpan.FromSeconds(10) };
            var health = new PortalHealth(http);
            var admin = new PortalAdminClient(http);

            var portal = await health.CheckPortalHealthAsync();
            var gateway = await health.CheckGatewayHealthAsync();
            Console.WriteLine($"Portal:  {(portal.Healthy ? "READY" : "NOT READY")} ({portal.Detail})");
            Console.WriteLine($"Gateway: {(gateway.Healthy ? "READY" : "NOT READY")} ({gateway.Detail})");

            try
            {
                await admin.LoginAsync(options.AdminEmail, options.AdminPassword);
                var agentJson = await admin.FindAgentByNameAsync(options.AgentDisplayName);
                var readiness = AgentReadinessEvaluator.Evaluate(agentJson, TimeSpan.FromSeconds(60), DateTimeOffset.UtcNow);
                Console.WriteLine($"Agent registered: {(readiness.State != AgentReadinessState.NotRegistered ? "YES" : "NO")}");
                Console.WriteLine($"Agent online:      {(readiness.ConnectivityStatus == "online" ? "YES" : "NO")}");
                Console.WriteLine($"Agent state:       {readiness.State}");
                Console.WriteLine($"Last heartbeat:    {readiness.LastSeenAtUtc?.ToString("O") ?? "never"}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Agent status unavailable: {ex.Message}");
            }

            var runtimeAvailable = RuntimeSeeder.IsRuntimeAvailable(options.DataDirectory, "python-core", "3.13", loggerFactory);
            Console.WriteLine($"Runtime (python-core/3.13): {(runtimeAvailable ? "READY" : "NOT READY")}");

            var pidFile = Path.Combine(repoRoot, "automation-agent", "certification-runs", "run", $"{PidFileName}.pid");
            Console.WriteLine($"Agent.Service PID file: {(File.Exists(pidFile) ? File.ReadAllText(pidFile).Split('\n')[0] : "(none)")}");

            return 0;
        }

        // -- run -----------------------------------------------------------

        private static readonly string[] BackgroundScenarios = { "echo", "fail", "timeout", "cancel", "progress", "artifact" };
        private static readonly string[] AllScenarios = BackgroundScenarios;

        internal static async Task<int> RunAsync(ILoggerFactory loggerFactory, ILogger logger, string[] args)
        {
            var (options, repoRoot) = Setup();
            var requested = args.Length == 0 || args[0] == "all"
                ? AllScenarios
                : args[0] == "background"
                    ? BackgroundScenarios
                    : new[] { args[0] };

            using var http = new HttpClient { BaseAddress = new Uri(options.PortalApiBaseUrl), Timeout = TimeSpan.FromSeconds(10) };
            var admin = new PortalAdminClient(http);
            await admin.LoginAsync(options.AdminEmail, options.AdminPassword);
            var agentJson = await admin.FindAgentByNameAsync(options.AgentDisplayName);
            var readiness = AgentReadinessEvaluator.Evaluate(agentJson, TimeSpan.FromSeconds(60), DateTimeOffset.UtcNow);
            if (!readiness.IsReady || readiness.AgentId is null)
            {
                logger.LogError("BLOCKED: Agent is not READY/DEGRADED. Run 'certification start' first.");
                return 3;
            }

            var runId = CertificationPaths.NextRunId(repoRoot, DateTime.UtcNow);
            var paths = new CertificationPaths(repoRoot, runId);
            paths.EnsureDirectoriesExist();

            var report = new CertificationReport { RunId = runId, StartedAtUtc = DateTimeOffset.UtcNow };
            report.Agent.Registered = true;
            report.Agent.Connected = readiness.ConnectivityStatus == "online";
            report.Agent.Ready = readiness.IsReady;
            report.Agent.AgentId = readiness.AgentId;
            report.Agent.ConnectivityStatus = readiness.ConnectivityStatus;
            report.Agent.HealthStatus = readiness.HealthStatus;
            report.Agent.LastSeenAtUtc = readiness.LastSeenAtUtc;

            var backendCli = new BackendCli(repoRoot);
            foreach (var scenario in requested)
            {
                logger.LogInformation("Running scenario certification.{Scenario}...", scenario);
                var scenarioResult = new ScenarioResult
                {
                    ScenarioId = $"certification.{scenario}",
                    Mode = CertificationMode.PortalE2E,
                    Status = ScenarioStatus.Blocked
                };

                try
                {
                    var created = await backendCli.CreateExecutionAsync(scenario, readiness.AgentId, runId);
                    var executionId = created.RootElement.GetProperty("execution_id").GetString();
                    scenarioResult.ExecutionId = executionId;

                    if (scenario == "cancel")
                    {
                        var running = await backendCli.WaitForStatusAsync(
                            executionId!,
                            "running",
                            Math.Min(30, options.ExecutionTimeoutSeconds));
                        var runningRoot = running.RootElement;
                        if (runningRoot.TryGetProperty("status", out var cancelBlockedStatus) && cancelBlockedStatus.GetString() == "BLOCKED")
                        {
                            scenarioResult.Status = ScenarioStatus.Blocked;
                            scenarioResult.Notes = runningRoot.TryGetProperty("reason", out var reason)
                                ? reason.GetString()
                                : "execution did not reach running before cancel";
                            logger.LogInformation("  certification.{Scenario} -> {Status}", scenario, scenarioResult.Status);
                            report.Scenarios.Add(scenarioResult);
                            continue;
                        }

                        await backendCli.CancelAsync(executionId!);
                        await backendCli.CancelAsync(executionId!);
                    }

                    var observed = await backendCli.WaitAsync(executionId!, options.ExecutionTimeoutSeconds);
                    var root = observed.RootElement;

                    if (root.TryGetProperty("status", out var blockedStatus) && blockedStatus.GetString() == "BLOCKED")
                    {
                        scenarioResult.Status = ScenarioStatus.Blocked;
                        scenarioResult.Notes = root.TryGetProperty("reason", out var reason) ? reason.GetString() : "harness wait timeout";
                    }
                    else
                    {
                        var portalStatus = root.GetProperty("status").GetString();
                        scenarioResult.PortalStatus = portalStatus;
                        scenarioResult.Status = ClassifyScenario(scenario, portalStatus, root);
                    }
                }
                catch (Exception ex)
                {
                    scenarioResult.Status = ScenarioStatus.Blocked;
                    scenarioResult.Notes = ex.Message;
                    logger.LogError(ex, "Scenario certification.{Scenario} could not be observed.", scenario);
                }

                logger.LogInformation("  certification.{Scenario} -> {Status}", scenario, scenarioResult.Status);
                report.Scenarios.Add(scenarioResult);
            }

            report.FinishedAtUtc = DateTimeOffset.UtcNow;
            report.Save(paths.ReportPath);

            Console.WriteLine();
            Console.WriteLine($"Run ID: {runId}");
            foreach (var s in report.Scenarios)
                Console.WriteLine($"  {s.ScenarioId,-24} {s.Status}");
            Console.WriteLine($"Overall gate: {report.OverallGate}");
            Console.WriteLine($"Report: {paths.ReportPath}");

            return report.OverallGate == "PASS" ? 0 : 1;
        }

        /// <summary>
        /// Item 51: never turn a harness timeout into PASS. Each scenario's
        /// expected terminal state is checked explicitly instead of
        /// assuming "not FAILED" means success.
        /// </summary>
        private static ScenarioStatus ClassifyScenario(string scenario, string? portalStatus, JsonElement observed)
        {
            switch (scenario)
            {
                case "echo":
                case "progress":
                case "artifact":
                    return portalStatus == "succeeded" ? ScenarioStatus.Pass : ScenarioStatus.Fail;

                case "fail":
                    if (portalStatus != "failed")
                        return ScenarioStatus.Fail;
                    var errorOutput = observed.TryGetProperty("error_output", out var e) ? e.GetString() ?? "" : "";
                    return errorOutput.Contains("CERTIFICATION_FAILURE", StringComparison.Ordinal)
                        ? ScenarioStatus.Pass
                        : ScenarioStatus.Fail;

                case "timeout":
                    return portalStatus == "timed_out" ? ScenarioStatus.Pass : ScenarioStatus.Fail;

                case "cancel":
                    return portalStatus == "cancelled" ? ScenarioStatus.Pass : ScenarioStatus.Fail;

                default:
                    return ScenarioStatus.NotApplicable;
            }
        }

        // -- stop ------------------------------------------------------------

        internal static async Task<int> StopAsync(ILoggerFactory loggerFactory, ILogger logger)
        {
            var (options, repoRoot) = Setup();
            var supervisor = new CertificationProcessSupervisor(loggerFactory.CreateLogger<CertificationProcessSupervisor>());
            var pidDirectory = Path.Combine(repoRoot, "automation-agent", "certification-runs", "run");
            var pidFile = Path.Combine(pidDirectory, $"{PidFileName}.pid");

            if (!File.Exists(pidFile))
            {
                logger.LogInformation("No running certification Agent.Service found (no PID file).");
                return 0;
            }

            var lines = await File.ReadAllLinesAsync(pidFile);
            if (lines.Length == 0 || !int.TryParse(lines[0], out var pid))
            {
                logger.LogWarning("PID file was unreadable; removing it.");
                File.Delete(pidFile);
                return 0;
            }

            var handle = new ManagedProcessHandle
            {
                Name = PidFileName,
                ProcessId = pid,
                StartedAtUtc = lines.Length > 1 && DateTime.TryParse(lines[1], out var started) ? started : DateTime.UtcNow,
                StdoutPath = Path.Combine(pidDirectory, "..", "current", "agent", $"{PidFileName}.stdout.log"),
                StderrPath = Path.Combine(pidDirectory, "..", "current", "agent", $"{PidFileName}.stderr.log"),
                PidFilePath = pidFile,
                SupportsGracefulStop = OperatingSystem.IsWindows()
            };

            var result = await supervisor.StopAsync(handle, TimeSpan.FromSeconds(options.GracefulShutdownTimeoutSeconds));
            logger.LogInformation(
                "Stopped Agent.Service (PID {Pid}). GracefulAttempted={Graceful} Forced={Forced} Duration={Duration}s",
                pid, result.GracefulShutdownAttempted, result.ForcedTermination, result.Duration.TotalSeconds);

            return result.ForcedTermination && !result.GracefulShutdownAttempted ? 1 : 0;
        }

        // -- clean -----------------------------------------------------------

        internal static async Task<int> CleanAsync(ILoggerFactory loggerFactory, ILogger logger, string[] args)
        {
            var (options, repoRoot) = Setup();
            var purgeRuntime = args.Contains("--purge-runtime");
            var purgeReports = args.Contains("--purge-reports");

            await StopAsync(loggerFactory, logger);

            if (Directory.Exists(options.DataDirectory))
            {
                foreach (var dir in new[] { "database", "downloads", "staging", "executions", "spool" })
                {
                    var path = Path.Combine(options.DataDirectory, dir);
                    if (Directory.Exists(path))
                    {
                        Directory.Delete(path, recursive: true);
                        logger.LogInformation("Removed {Path}", path);
                    }
                }

                if (purgeRuntime)
                {
                    var runtimesPath = Path.Combine(options.DataDirectory, "store", "runtimes");
                    if (Directory.Exists(runtimesPath))
                    {
                        Directory.Delete(runtimesPath, recursive: true);
                        logger.LogInformation("Removed runtime store {Path} (--purge-runtime)", runtimesPath);
                    }
                }
            }

            if (purgeReports)
            {
                var runsRoot = Path.Combine(repoRoot, "automation-agent", "certification-runs");
                if (Directory.Exists(runsRoot))
                {
                    foreach (var dir in Directory.GetDirectories(runsRoot, "cert_*"))
                        Directory.Delete(dir, recursive: true);
                    logger.LogInformation("Removed certification run reports under {Path} (--purge-reports)", runsRoot);
                }
            }
            else
            {
                logger.LogInformation("Kept certification-runs/*/report.json and logs (item 57). Pass --purge-reports to remove them.");
            }

            logger.LogInformation("clean complete.");
            return 0;
        }
    }
}
