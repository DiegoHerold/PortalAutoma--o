using Biason.AutomationAgent.Application.Registration;
using Biason.AutomationAgent.Domain.Agents;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Registration;

public sealed class AgentRegistrationTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync() => await _helper.InitializeDatabaseAsync();

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    // === Fábrica do sujeito sob teste ===

    private (AgentRegistrationService Service, IPortalApiClient Portal, IAgentCredentialStore Store)
        CreateService(
            IPortalApiClient? portal = null,
            string? registrationToken = "token-de-registro",
            bool portalEnabled = true)
    {
        portal ??= Substitute.For<IPortalApiClient>();
        var store = _helper.CreateCredentialStore();
        var identity = _helper.CreateIdentityRepository();

        var osInfo = Substitute.For<IOsInfoCollector>();
        osInfo.Collect().Returns(new OsInfo
        {
            Name = "Windows 11 Pro",
            Architecture = "x64",
            Hostname = "PC-TESTE",
            AgentVersion = "0.3.0"
        });

        var portalOptions = Options.Create(new PortalOptions
        {
            Enabled = portalEnabled,
            ApiBaseUrl = "https://portal.example/api",
            WebSocketUrl = "wss://portal.example/agents/connect",
            RegistrationToken = registrationToken
        });

        var service = new AgentRegistrationService(
            identity, store, portal, osInfo,
            portalOptions,
            Options.Create(new AgentOptions { Version = "0.3.0" }),
            _helper.Clock,
            NullLogger<AgentRegistrationService>.Instance);

        return (service, portal, store);
    }

    private static PortalRegistrationOutcome SuccessOutcome(
        string agentId = "agt_789",
        string secret = "credencial-secreta",
        DateTime? expiresAt = null)
    {
        return PortalRegistrationOutcome.Ok(
            agentId,
            new AgentCredential
            {
                Type = "client_token",
                Value = secret,
                ExpiresAtUtc = expiresAt ?? DateTime.UtcNow.AddDays(90),
                StoredAtUtc = DateTime.UtcNow
            },
            new PortalEndpoints("wss://portal.example/agents/connect", "https://portal.example/api"));
    }

    // === agent-registration ===

    [Fact]
    public async Task Register_PersistsAgentIdAndCredential()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome());

        var (service, _, store) = CreateService(portal);

        var result = await service.EnsureRegisteredAsync();

        result.Outcome.Should().Be(RegistrationOutcome.Registered);
        result.AgentId.Should().Be("agt_789");

        // agent_id persistido na identidade
        var identity = await _helper.CreateIdentityRepository().GetIdentityAsync();
        identity!.AgentId.Should().Be("agt_789");
        identity.IsRegistered.Should().BeTrue();
        identity.RegisteredAtUtc.Should().NotBeNull();

        // credencial recuperável
        var credential = await store.GetAsync();
        credential!.Value.Should().Be("credencial-secreta");
    }

    [Fact]
    public async Task Register_SendsIdentityFieldsToPortal()
    {
        AgentRegistrationRequest? captured = null;
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Do<AgentRegistrationRequest>(r => captured = r), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome());

        var (service, _, _) = CreateService(portal);
        await service.EnsureRegisteredAsync();

        captured.Should().NotBeNull();
        captured!.InstallationId.Should().StartWith("ins_");
        captured.MachineId.Should().StartWith("mch_");
        captured.AgentVersion.Should().Be("0.3.0");
        captured.OperatingSystemName.Should().Be("Windows 11 Pro");
        captured.RegistrationToken.Should().Be("token-de-registro");
    }

    // === registration-idempotent ===

    [Fact]
    public async Task SecondStartup_DoesNotRegisterAgain()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome());

        var (first, _, _) = CreateService(portal);
        var firstResult = await first.EnsureRegisteredAsync();
        firstResult.Outcome.Should().Be(RegistrationOutcome.Registered);

        // Simula reinicialização: novo serviço, mesmo banco.
        var (second, _, _) = CreateService(portal);
        var secondResult = await second.EnsureRegisteredAsync();

        secondResult.Outcome.Should().Be(RegistrationOutcome.AlreadyRegistered);
        secondResult.AgentId.Should().Be("agt_789");

        await portal.Received(1).RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task RepeatedCalls_InSameProcess_RegisterOnlyOnce()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome());

        var (service, _, _) = CreateService(portal);

        await service.EnsureRegisteredAsync();
        await service.EnsureRegisteredAsync();
        await service.EnsureRegisteredAsync();

        await portal.Received(1).RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>());
    }

    // === invalid-registration-token ===

    [Fact]
    public async Task InvalidToken_IsRejectedWithoutPersistingAnything()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(PortalRegistrationOutcome.Rejected(
                  "INVALID_REGISTRATION_TOKEN", "Token inválido."));

        var (service, _, store) = CreateService(portal);

        var result = await service.EnsureRegisteredAsync();

        result.Outcome.Should().Be(RegistrationOutcome.Rejected);
        result.ReasonCode.Should().Be("INVALID_REGISTRATION_TOKEN");
        result.Retryable.Should().BeFalse();

        // Nada foi persistido: nem agent_id nem credencial.
        var identity = await _helper.CreateIdentityRepository().GetIdentityAsync();
        identity!.AgentId.Should().BeNull();
        (await store.GetAsync()).Should().BeNull();
    }

    [Fact]
    public async Task TransientFailure_IsMarkedRetryable()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(PortalRegistrationOutcome.Transient("PORTAL_UNREACHABLE", "Timeout."));

        var (service, _, _) = CreateService(portal);
        var result = await service.EnsureRegisteredAsync();

        result.Outcome.Should().Be(RegistrationOutcome.Failed);
        result.Retryable.Should().BeTrue();
    }

    [Fact]
    public async Task NoRegistrationToken_ReportsNotConfigured()
    {
        var (service, portal, _) = CreateService(registrationToken: null);

        var result = await service.EnsureRegisteredAsync();

        result.Outcome.Should().Be(RegistrationOutcome.NotConfigured);
        await portal.DidNotReceive().RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task PortalDisabled_SkipsRegistrationEntirely()
    {
        var (service, portal, _) = CreateService(portalEnabled: false);

        var result = await service.EnsureRegisteredAsync();

        result.Outcome.Should().Be(RegistrationOutcome.NotConfigured);
        await portal.DidNotReceive().RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>());
    }

    // === Revogação e expiração forçam novo registro ===

    [Fact]
    public async Task RevokedCredential_TriggersReRegistration()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome());

        var (service, _, store) = CreateService(portal);
        await service.EnsureRegisteredAsync();

        await store.RevokeAsync("revogada pelo Portal");

        var (afterRevoke, _, _) = CreateService(portal);
        var result = await afterRevoke.EnsureRegisteredAsync();

        result.Outcome.Should().Be(RegistrationOutcome.Registered);
        await portal.Received(2).RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task ExpiredCredential_TriggersReRegistration()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome(expiresAt: DateTime.UtcNow.AddMinutes(-1)));

        var (service, _, _) = CreateService(portal);
        await service.EnsureRegisteredAsync();

        var (again, _, _) = CreateService(portal);
        await again.EnsureRegisteredAsync();

        await portal.Received(2).RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task ForceRegister_DiscardsExistingCredential()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome(secret: "primeira"), SuccessOutcome(agentId: "agt_novo", secret: "segunda"));

        var (service, _, store) = CreateService(portal);
        await service.EnsureRegisteredAsync();
        (await store.GetAsync())!.Value.Should().Be("primeira");

        var result = await service.ForceRegisterAsync();

        result.Outcome.Should().Be(RegistrationOutcome.Registered);
        (await store.GetAsync())!.Value.Should().Be("segunda");
    }

    [Fact]
    public async Task IsRegistered_ReflectsPersistedState()
    {
        var portal = Substitute.For<IPortalApiClient>();
        portal.RegisterAsync(Arg.Any<AgentRegistrationRequest>(), Arg.Any<CancellationToken>())
              .Returns(SuccessOutcome());

        var (service, _, _) = CreateService(portal);

        (await service.IsRegisteredAsync()).Should().BeFalse();
        await service.EnsureRegisteredAsync();
        (await service.IsRegisteredAsync()).Should().BeTrue();
    }
}
