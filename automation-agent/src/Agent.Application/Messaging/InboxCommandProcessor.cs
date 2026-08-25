using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class InboxCommandProcessor : BackgroundService
{
    private readonly IInboxRepository _inbox;
    private readonly IReadOnlyDictionary<string, IInboxCommandHandler> _handlers;
    private readonly PortalInboxService _inboxService;
    private readonly IClock _clock;
    private readonly MessagingOptions _options;
    private readonly ILogger<InboxCommandProcessor> _logger;

    public InboxCommandProcessor(
        IInboxRepository inbox,
        IEnumerable<IInboxCommandHandler> handlers,
        PortalInboxService inboxService,
        IClock clock,
        IOptions<MessagingOptions> options,
        ILogger<InboxCommandProcessor> logger)
    {
        _inbox = inbox;
        _handlers = handlers
            .GroupBy(h => h.MessageType, StringComparer.Ordinal)
            .ToDictionary(g => g.Key, g => g.First(), StringComparer.Ordinal);
        _inboxService = inboxService;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(_options.PollIntervalSeconds));

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await ProcessOnceAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Inbox command processor cycle failed.");
            }

            try { await timer.WaitForNextTickAsync(stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
    }

    public async Task<int> ProcessOnceAsync(CancellationToken ct = default)
    {
        var pending = await _inbox.GetPendingBatchAsync(_options.OutboxBatchSize, ct);
        var processed = 0;

        foreach (var command in pending)
        {
            if (!_handlers.TryGetValue(command.CommandType, out var handler))
            {
                // Comando persistido sem handler correspondente não pode ficar
                // `pending` indefinidamente (seção 41 do Bloco 5.5). Dead-letter
                // explícito + ACK, para que o Portal saiba que o comando não será
                // processado em vez de aguardar silenciosamente para sempre.
                _logger.LogWarning(
                    "No handler registered for command type {CommandType} (message {MessageId}); dead-lettering as UNSUPPORTED_COMMAND.",
                    command.CommandType, command.MessageId);

                await _inbox.MarkDeadLetterAsync(command.Id, _clock.UtcNow, "UNSUPPORTED_COMMAND", ct);
                await _inboxService.EnqueueCommandAckAsync(command, InboxCommandStatus.DeadLetter, duplicate: false, "UNSUPPORTED_COMMAND");
                processed++;
                continue;
            }

            var nextAttempt = command.AttemptCount + 1;
            await _inbox.MarkProcessingAsync(command.Id, ct);

            try
            {
                var result = await handler.HandleAsync(command, ct);
                if (result.Success)
                {
                    await _inbox.MarkProcessedAsync(command.Id, _clock.UtcNow, result.Result, ct);
                    await _inboxService.EnqueueCommandAckAsync(command, InboxCommandStatus.Processed, duplicate: false, result.Result);
                }
                else if (result.DeadLetter)
                {
                    await _inbox.MarkDeadLetterAsync(command.Id, _clock.UtcNow, result.Error ?? "Command handler dead-lettered the command", ct);
                    await _inboxService.EnqueueCommandAckAsync(command, InboxCommandStatus.DeadLetter, duplicate: false, result.Error);
                }
                else
                {
                    await _inbox.MarkPendingAsync(command.Id, result.Error ?? "Command handler requested retry", ct);
                }

                processed++;
            }
            catch (Exception ex)
            {
                if (nextAttempt >= _options.MaxAttempts)
                {
                    _logger.LogError(
                        ex,
                        "Command handler for {CommandType} (message {MessageId}) failed permanently on attempt {Attempt}/{MaxAttempts}; dead-lettering.",
                        command.CommandType,
                        command.MessageId,
                        nextAttempt,
                        _options.MaxAttempts);
                    await _inbox.MarkDeadLetterAsync(command.Id, _clock.UtcNow, ex.Message, CancellationToken.None);
                    await _inboxService.EnqueueCommandAckAsync(command, InboxCommandStatus.DeadLetter, duplicate: false, ex.Message);
                    processed++;
                }
                else
                {
                    _logger.LogWarning(
                        ex,
                        "Command handler for {CommandType} (message {MessageId}) failed on attempt {Attempt}/{MaxAttempts}; scheduling retry.",
                        command.CommandType,
                        command.MessageId,
                        nextAttempt,
                        _options.MaxAttempts);
                    await _inbox.MarkPendingAsync(command.Id, ex.Message, CancellationToken.None);
                }
            }
        }

        return processed;
    }
}
