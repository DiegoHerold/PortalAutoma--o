using System.Text.Json;
using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Application.Interactive;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Infrastructure.Clock;
using Biason.AutomationAgent.Infrastructure.Database;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.Infrastructure.Storage;
using Biason.AutomationAgent.Windows.Collectors;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Service;

public static class EarlySessionCli
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true
    };

    public static async Task<bool> TryHandleAsync(string[] args, CancellationToken ct)
    {
        if (!SessionCliHandler.IsSessionCommand(args))
            return false;

        var config = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile($"appsettings.{Environment.GetEnvironmentVariable("DOTNET_ENVIRONMENT") ?? "Production"}.json", optional: true)
            .AddEnvironmentVariables("AUTOMATION_AGENT_")
            .Build();

        var sessionRunnerOptions = Bind<SessionRunnerOptions>(config, SessionRunnerOptions.Section);

        if (args.Contains("pipe", StringComparer.OrdinalIgnoreCase) &&
            (args.Contains("status", StringComparer.OrdinalIgnoreCase) || args.Contains("test", StringComparer.OrdinalIgnoreCase)))
        {
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                pipe_name = sessionRunnerOptions.PipeName,
                started_at_utc = (DateTime?)null,
                active_connections = 0,
                acl_mode = "current_user_only",
                last_error = (string?)null,
                host_started = false
            }, JsonOpts));
            return true;
        }

        var databaseOptions = Bind<DatabaseOptions>(config, DatabaseOptions.Section);
        var developmentOptions = Bind<DevelopmentOptions>(config, DevelopmentOptions.Section);
        var dirs = new AgentDirectoryResolver(NullLogger<AgentDirectoryResolver>.Instance, developmentOptions.DataDirectory);

        if (!dirs.Validate(out var errors))
        {
            Console.Error.WriteLine($"Directory validation failed: {string.Join("; ", errors)}");
            Environment.ExitCode = 2;
            return true;
        }

        dirs.EnsureDirectoriesExist();

        using var db = new SqliteDatabaseManager(
            dirs,
            Options.Create(databaseOptions),
            NullLogger<SqliteDatabaseManager>.Instance);
        await db.InitializeAsync(ct);

        var sessions = new InteractiveSessionRepository(db);
        var runners = new SessionRunnerRepository(db);
        var connections = new SessionRunnerConnectionRepository(db);
        var locks = new DesktopLockRepository(db);
        var assignments = new InteractiveExecutionAssignmentRepository(db);
        var clock = new SystemClock();

        if (args.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("list", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await sessions.GetAllAsync(ct), JsonOpts));
            return true;
        }

        if (args.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("show", StringComparer.OrdinalIgnoreCase))
        {
            var idText = args.SkipWhile(a => !a.Equals("show", StringComparison.OrdinalIgnoreCase)).Skip(1).FirstOrDefault();
            var session = int.TryParse(idText, out var id)
                ? await sessions.GetAsync(id, ct)
                : null;
            Console.WriteLine(JsonSerializer.Serialize(session, JsonOpts));
            return true;
        }

        if (args.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("select", StringComparer.OrdinalIgnoreCase))
        {
            var desktop = new WindowsDesktopStateReader(NullLogger<WindowsDesktopStateReader>.Instance);
            var discovery = new WindowsSessionDiscovery(desktop, NullLogger<WindowsSessionDiscovery>.Instance);
            var selector = new InteractiveSessionSelector(sessions, discovery);
            var selected = await selector.SelectAsync(new InteractiveSessionSelectionRequest
            {
                Policy = InteractiveSessionSelectionPolicy.ActiveUnlocked
            }, ct);
            Console.WriteLine(JsonSerializer.Serialize(selected, JsonOpts));
            return true;
        }

        if (args.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("capabilities", StringComparer.OrdinalIgnoreCase))
        {
            var capabilityService = new SessionCapabilityService(sessions, clock);
            Console.WriteLine(JsonSerializer.Serialize(await capabilityService.GetCapabilitiesAsync(ct), JsonOpts));
            return true;
        }

        if (args.Contains("session-runner", StringComparer.OrdinalIgnoreCase) &&
            (args.Contains("list", StringComparer.OrdinalIgnoreCase) || args.Contains("status", StringComparer.OrdinalIgnoreCase)))
        {
            var payload = new
            {
                runners = await runners.GetAllAsync(ct),
                connections = await connections.GetRecentAsync(20, ct)
            };
            Console.WriteLine(JsonSerializer.Serialize(payload, JsonOpts));
            return true;
        }

        if (args.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("status", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                active = await assignments.CountActiveAsync(ct),
                assignments = await assignments.GetActiveAsync(ct)
            }, JsonOpts));
            return true;
        }

        if (args.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("sessions", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await sessions.GetAllAsync(ct), JsonOpts));
            return true;
        }

        if (args.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("locks", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await locks.GetAllAsync(ct), JsonOpts));
            return true;
        }

        if (args.Contains("desktop", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("status", StringComparer.OrdinalIgnoreCase))
        {
            var capabilityService = new SessionCapabilityService(sessions, clock);
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                sessions = await sessions.GetAllAsync(ct),
                capabilities = await capabilityService.GetCapabilitiesAsync(ct)
            }, JsonOpts));
            return true;
        }

        if (args.Contains("desktop", StringComparer.OrdinalIgnoreCase) &&
            args.Contains("screenshot", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                captured = false,
                reason = "manual screenshot capture is reserved for active interactive executions"
            }, JsonOpts));
            return true;
        }

        if ((args.Contains("excel", StringComparer.OrdinalIgnoreCase) ||
             args.Contains("dominio", StringComparer.OrdinalIgnoreCase)) &&
            args.Contains("capability", StringComparer.OrdinalIgnoreCase))
        {
            var key = args.Contains("excel", StringComparer.OrdinalIgnoreCase) ? "office.excel" : "dominio.installed";
            var capabilityService = new SessionCapabilityService(sessions, clock);
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                key,
                session = (await capabilityService.GetCapabilitiesAsync(ct)).Where(c => string.Equals(c.Key, key, StringComparison.OrdinalIgnoreCase))
            }, JsonOpts));
            return true;
        }

        return false;
    }

    private static T Bind<T>(IConfiguration config, string sectionName) where T : new()
    {
        var value = new T();
        config.GetSection(sectionName).Bind(value);
        return value;
    }
}
