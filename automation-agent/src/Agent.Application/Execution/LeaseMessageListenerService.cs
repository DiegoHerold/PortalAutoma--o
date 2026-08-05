using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Execution;

/// <summary>
/// Consome execution.lease_renewed / execution.lease_granted /
/// execution.lease_expired vindas do Portal (Bloco 5.5, seção 9/19). Essas
/// mensagens são Inbound mas não fazem parte de <c>PortalMessageTypes.Commands</c>
/// (não passam pela Inbox nem por um IInboxCommandHandler — ver
/// PortalInboxService, que ignora tudo fora de Commands), então são
/// consumidas diretamente do evento <see cref="IPortalConnectionManager.MessageReceived"/>,
/// no mesmo padrão de <c>PortalMessageAcknowledgementService</c> e
/// <c>HeartbeatService</c>.
/// </summary>
public sealed class LeaseMessageListenerService : IHostedService
{
    private readonly IPortalConnectionManager _connection;
    private readonly IExecutionLeaseManager _leaseManager;
    private readonly ILogger<LeaseMessageListenerService> _logger;

    public LeaseMessageListenerService(
        IPortalConnectionManager connection,
        IExecutionLeaseManager leaseManager,
        ILogger<LeaseMessageListenerService> logger)
    {
        _connection = connection;
        _leaseManager = leaseManager;
        _logger = logger;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _connection.MessageReceived += HandleMessageAsync;
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _connection.MessageReceived -= HandleMessageAsync;
        return Task.CompletedTask;
    }

    public async Task HandleMessageAsync(InboundPortalMessage message)
    {
        switch (message.MessageType)
        {
            case PortalMessageTypes.LeaseRenewed:
            case PortalMessageTypes.LeaseGranted:
            {
                var payload = ProtocolJson.ReadPayload<LeaseGrantPayload>(message.Payload);
                if (payload is null || string.IsNullOrEmpty(payload.LeaseId) || string.IsNullOrEmpty(payload.ExecutionAttemptId))
                {
                    _logger.LogWarning("{MessageType} with invalid payload (message {MessageId}); ignoring.", message.MessageType, message.MessageId);
                    return;
                }

                await _leaseManager.HandleLeaseGrantedAsync(payload.LeaseId, payload.ExecutionAttemptId, payload.ExpiresAt, CancellationToken.None);
                return;
            }

            case PortalMessageTypes.LeaseExpired:
            {
                var payload = ProtocolJson.ReadPayload<LeaseExpiredNoticePayload>(message.Payload);
                if (payload is null || string.IsNullOrEmpty(payload.LeaseId) || string.IsNullOrEmpty(payload.ExecutionAttemptId))
                {
                    _logger.LogWarning("{MessageType} with invalid payload (message {MessageId}); ignoring.", message.MessageType, message.MessageId);
                    return;
                }

                await _leaseManager.HandleLeaseExpiredAsync(payload.LeaseId, payload.ExecutionAttemptId, payload.Reason, CancellationToken.None);
                return;
            }

            default:
                return;
        }
    }
}
