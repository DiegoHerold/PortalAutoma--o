using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Application.Messaging.Handlers;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Protocol.Messages;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Messaging;

/// <summary>
/// Bloco 5.5, seção 48 — "handler registry": confirma que os quatro handlers
/// obrigatórios existem, implementam <see cref="IInboxCommandHandler"/> e
/// declaram o MessageType correspondente ao catálogo do protocolo. Isso é o
/// que permite o registro em DI (Program.cs) resolver
/// <c>IEnumerable&lt;IInboxCommandHandler&gt;</c> corretamente para o
/// InboxCommandProcessor.
///
/// A partir dos Incrementos 3/4, ExecutionOfferHandler/ExecutionCommitHandler/
/// ExecutionCancelRequestedHandler passaram a ter implementação real (não são
/// mais stubs parameterless) — este teste só verifica a declaração de
/// MessageType, então as dependências são substituídas por dublês (NSubstitute)
/// só para permitir a construção; nenhuma delas é exercitada.
/// </summary>
public sealed class ExecutionCommandHandlersTests
{
    [Fact]
    public void ExecutionOfferHandler_DeclaresExecutionOfferMessageType()
    {
        IInboxCommandHandler handler = CreateOfferHandler();
        handler.MessageType.Should().Be(PortalMessageTypes.ExecutionOffer);
    }

    [Fact]
    public void ExecutionCommitHandler_DeclaresExecutionCommitMessageType()
    {
        IInboxCommandHandler handler = CreateCommitHandler();
        handler.MessageType.Should().Be(PortalMessageTypes.ExecutionCommit);
    }

    [Fact]
    public void ExecutionCancelRequestedHandler_DeclaresExecutionCancelRequestedMessageType()
    {
        IInboxCommandHandler handler = CreateCancelHandler();
        handler.MessageType.Should().Be(PortalMessageTypes.ExecutionCancelRequested);
    }

    [Fact]
    public void AgentSyncRequestHandler_DeclaresSyncRequestMessageType()
    {
        IInboxCommandHandler handler = CreateSyncHandler();
        handler.MessageType.Should().Be(PortalMessageTypes.SyncRequest);
    }

    [Fact]
    public void ArtifactConfirmedHandler_DeclaresArtifactConfirmedMessageType()
    {
        IInboxCommandHandler handler = CreateArtifactConfirmedHandler();
        handler.MessageType.Should().Be(PortalMessageTypes.ArtifactConfirmed);
    }

    [Fact]
    public void AllHandlers_CoverAllCommandsInPortalMessageTypes()
    {
        // PortalMessageTypes.Commands é o conjunto fechado de comandos que exigem
        // handler (seção 41). Se um novo comando for adicionado a esse conjunto
        // sem handler correspondente, este teste falha — evita regressão para o
        // bug original (comando sem handler ficando pending para sempre).
        var handlerTypes = new IInboxCommandHandler[]
        {
            CreateOfferHandler(),
            CreateCommitHandler(),
            CreateCancelHandler(),
            CreateSyncHandler(),
            CreateArtifactConfirmedHandler()
        }.Select(h => h.MessageType).ToHashSet(StringComparer.Ordinal);

        foreach (var command in PortalMessageTypes.Commands)
        {
            handlerTypes.Should().Contain(command, $"o comando '{command}' precisa de um IInboxCommandHandler registrado");
        }
    }

    private static ExecutionOfferHandler CreateOfferHandler() => new(
        Substitute.For<IExecutionOfferRepository>(),
        Substitute.For<IExecutionRepository>(),
        Substitute.For<IPackageStore>(),
        Substitute.For<IManifestValidator>(),
        Substitute.For<IAdmissionController>(),
        Substitute.For<IResourceReservationManager>(),
        Substitute.For<IAgentIdentityService>(),
        CreateOutboxPublisher(),
        Substitute.For<IDownloadManager>(),
        Substitute.For<IDirectoryResolver>(),
        Substitute.For<IClock>(),
        NullLogger<ExecutionOfferHandler>.Instance);

    private static ExecutionCommitHandler CreateCommitHandler() => new(
        Substitute.For<IExecutionCommitRepository>(),
        Substitute.For<IExecutionRepository>(),
        Substitute.For<IExecutionOfferRepository>(),
        Substitute.For<IExecutionLeaseRepository>(),
        Substitute.For<IResourceReservationManager>(),
        Substitute.For<IPackageStore>(),
        Substitute.For<IManifestValidator>(),
        Substitute.For<IExecutionManager>(),
        CreateOutboxPublisher(),
        Substitute.For<IClock>(),
        NullLogger<ExecutionCommitHandler>.Instance);

    private static ExecutionCancelRequestedHandler CreateCancelHandler() => new(
        Substitute.For<IExecutionRepository>(),
        Substitute.For<IResourceReservationManager>(),
        Substitute.For<IExecutionManager>(),
        CreateOutboxPublisher(),
        Substitute.For<IClock>(),
        NullLogger<ExecutionCancelRequestedHandler>.Instance);

    private static AgentSyncRequestHandler CreateSyncHandler() => new(
        Substitute.For<IAgentSyncService>());

    private static ArtifactConfirmedHandler CreateArtifactConfirmedHandler() => new(
        Substitute.For<IPendingArtifactRepository>(),
        Substitute.For<IClock>(),
        NullLogger<ArtifactConfirmedHandler>.Instance);

    private static OutboxMessagePublisher CreateOutboxPublisher() => new(
        Substitute.For<IOutboxRepository>(),
        Substitute.For<IAgentIdentityService>(),
        Substitute.For<IClock>());
}
