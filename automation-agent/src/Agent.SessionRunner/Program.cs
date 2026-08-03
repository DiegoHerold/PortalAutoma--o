using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.SessionRunner;
using Biason.AutomationAgent.Windows.Collectors;
using Microsoft.Extensions.Options;

var builder = Host.CreateApplicationBuilder(args);

builder.Configuration
    .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
    .AddEnvironmentVariables("AUTOMATION_AGENT_");

builder.Services.AddOptions<SessionRunnerOptions>()
    .Bind(builder.Configuration.GetSection(SessionRunnerOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<LocalProtocolOptions>()
    .Bind(builder.Configuration.GetSection(LocalProtocolOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddSingleton<IDesktopStateReader, WindowsDesktopStateReader>();
builder.Services.AddSingleton<IWindowsSessionDiscovery, WindowsSessionDiscovery>();
builder.Services.AddSingleton<SessionRunnerPipeClient>();
builder.Services.AddSingleton<InteractiveExecutionHostRunner>();
builder.Services.AddHostedService<SessionRunnerWorker>();

builder.Services.AddLogging(logging => logging.AddSimpleConsole(options =>
{
    options.SingleLine = true;
    options.TimestampFormat = "HH:mm:ss ";
}));

var host = builder.Build();
await host.RunAsync();
