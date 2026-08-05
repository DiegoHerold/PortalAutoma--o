using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Messaging.Handlers;

/// <summary>
/// Processa <c>execution.cancel_requested</c> vindo do Portal (Bloco 5.5,
/// seção 20). Cobre os grupos de estado da execução:
///
///   - Terminal (Succeeded/Rejected/Cancelled/Failed/TimedOut/Orphaned):
///     idempotente — não reenvia evento, o Portal já recebeu o evento final
///     correspondente quando a execução chegou lá.
///   - Offered: janela transitória (o <see cref="ExecutionOfferHandler"/>
///     decide Reserved/Rejected de forma síncrona antes de responder ao
///     Portal, então este estado não deveria ser observável externamente).
///     Offered-&gt;Cancelled não é uma transição legal na máquina de estados;
///     se essa corrida acontecer, devolve erro retryable em vez de arriscar
///     estado inconsistente.
///   - Reserved/Committed/Preparing/Starting: a máquina de estados permite
///     salto direto para Cancelled. Cancelamento síncrono: libera reserva e
///     locks, avisa ExecutionManager.CancelAsync por segurança (cobre o caso
///     de Starting já ter lançado um processo) e confirma via
///     execution.cancelled.
///   - CancelRequested/Cancelling: já em cancelamento — reenvia
///     execution.cancelling e sinaliza de novo (idempotente, cobre
///     reentrega at-least-once do Portal).
///   - Running: este handler NÃO transiciona o ExecutionRecord. A instância
///     que <c>ExecutionManager.ExecuteAsync</c> mantém em memória é um objeto diferente do que este handler carrega
///     do repositório — escrever CurrentState aqui arriscaria uma
///     sobrescrita perdida contra a transição que ExecuteAsync fará quando
///     observar o cancelamento. Este handler apenas confirma o pedido
///     (execution.cancelling) e repassa o sinal via
///     ExecutionManager.CancelAsync; a transição real
///     (CancelRequested-&gt;Cancelling-&gt;Cancelled) e o evento final
///     (execution.cancelled ou execution.failed) são responsabilidade do
///     próprio ExecuteAsync e do wrapper fire-and-forget do
///     ExecutionCommitHandler.
///
/// Nota: o payload de execution.cancel_requested não carrega um identificador
/// de tentativa que sobreviva além do commit — ExecutionManager.ExecuteAsync
/// substitui ExecutionRecord.CurrentAttemptId pelo seu próprio attempt_id
/// gerado localmente assim que a execução entra em Preparing (rastreamento
/// de tentativa é um conceito agent-local, distinto do execution_attempt_id
/// do Portal). Por isso este handler não valida attempt_id contra o estado
/// persistido — usa apenas CurrentState, que é suficiente já que não existe
/// hoje um fluxo de múltiplas tentativas concorrentes para a mesma execução.
///
/// Não reimplementa cancelamento — reaproveita CancellationManager (via
/// ExecutionManager.CancelAsync) e ExecutionTransitions.
/// </summary>
public sealed class ExecutionCancelRequestedHandler : IInboxCommandHandler
{
    private readonly IExecutionRepository _execRepo;
    private readonly IResourceReservationManager _reservations;
    private readonly IExecutionManager _executionManager;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IDesktopLockManager? _desktopLocks;
    private readonly IClock _clock;
    private readonly ILogger<ExecutionCancelRequestedHandler> _logger;

    public ExecutionCancelRequestedHandler(
        IExecutionRepository execRepo,
        IResourceReservationManager reservations,
        IExecutionManager executionManager,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        ILogger<ExecutionCancelRequestedHandler> logger,
        IDesktopLockManager? desktopLocks = null)
    {
        _execRepo = execRepo;
        _reservations = reservations;
        _executionManager = executionManager;
        _outboxPublisher = outboxPublisher;
        _clock = clock;
        _logger = logger;
        _desktopLocks = desktopLocks;
    }

    public string MessageType => PortalMessageTypes.ExecutionCancelRequested;

    public async Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default)
    {
        var payload = ProtocolJson.Deserialize<ExecutionCancelRequestedPayload>(command.PayloadJson);
        if (payload is null || string.IsNullOrEmpty(payload.ExecutionAttemptId) || string.IsNullOrEmpty(payload.Reason))
        {
            _logger.LogWarning("execution.cancel_requested with invalid payload (message {MessageId})", command.MessageId);
            return InboxCommandHandlerResult.Dead("INVALID_CANCEL_PAYLOAD");
        }

        var attemptId = command.ExecutionAttemptId ?? payload.ExecutionAttemptId;
        var executionId = command.ExecutionId ?? payload.ExecutionId;
        if (string.IsNullOrEmpty(attemptId) || string.IsNullOrEmpty(executionId))
        {
            _logger.LogWarning("execution.cancel_requested without execution_id/execution_attempt_id (message {MessageId})", command.MessageId);
            return InboxCommandHandlerResult.Dead("INVALID_CANCEL_ENVELOPE");
        }

        var execution = await _execRepo.GetAsync(executionId, ct);
        if (execution is null)
        {
            return InboxCommandHandlerResult.Dead("EXECUTION_NOT_FOUND");
        }

        var state = execution.CurrentState;

        if (ExecutionStateMachine.IsTerminal(state))
        {
            _logger.LogInformation(
                "execution.cancel_requested for {ExecutionId}/{AttemptId} arrived after execution reached terminal state {State}; ignoring (already final).",
                executionId, attemptId, state);
            return InboxCommandHandlerResult.Processed($"cancel_ignored_already_{state}");
        }

        if (state == ExecutionState.CancelRequested || state == ExecutionState.Cancelling)
        {
            await SendCancellingAsync(executionId, attemptId, ct);
            await _executionManager.CancelAsync(executionId, ct);
            return InboxCommandHandlerResult.Processed("cancel_already_in_progress");
        }

        if (state == ExecutionState.Offered)
        {
            _logger.LogWarning(
                "execution.cancel_requested arrived while execution {ExecutionId} is still Offered (race); asking Portal to retry.",
                executionId);
            return InboxCommandHandlerResult.Dead("EXECUTION_STATE_TRANSIENT");
        }

        // Reserved/Committed/Preparing/Starting permitem salto direto para
        // Cancelled na máquina de estados; Running não (só via
        // CancelRequested->Cancelling, tratado no ramo abaixo). Consultar
        // ExecutionStateMachine diretamente em vez de manter uma lista de
        // estados paralela evita as duas ficarem dessincronizadas.
        if (ExecutionStateMachine.CanTransition(state, ExecutionState.Cancelled))
        {
            await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Cancelled, ct);

            if (execution.ReservationId is not null)
                await _reservations.ReleaseAsync(execution.ReservationId, CancellationToken.None);

            if (_desktopLocks is not null)
            {
                try { await _desktopLocks.ReleaseAsync(executionId, attemptId, CancellationToken.None); }
                catch (Exception ex) { _logger.LogWarning(ex, "Failed to release desktop locks after cancel for {ExecutionId}/{AttemptId}", executionId, attemptId); }
            }

            // Best-effort: cobre o caso de Starting já ter lançado o processo
            // (ExecuteAsync registra o ProcessHandle antes de transicionar
            // para Running) ou de ExecuteAsync estar em voo concorrente para
            // esta execução. Se nada estiver rodando ainda, é um no-op
            // (CancellationManager apenas loga um aviso).
            await _executionManager.CancelAsync(executionId, CancellationToken.None);

            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.ExecutionCancelled,
                new { ExecutionId = executionId, ExecutionAttemptId = attemptId, Reason = payload.Reason },
                executionId: executionId,
                executionAttemptId: attemptId,
                ct: ct);

            _logger.LogInformation(
                "execution.cancel_requested applied: execution={ExecutionId}, attempt={AttemptId}, previousState={PreviousState}",
                executionId, attemptId, state);

            return InboxCommandHandlerResult.Processed("cancelled");
        }

        // Running (único estado restante não coberto acima): ver nota na
        // documentação da classe sobre por que o ExecutionRecord não é
        // transicionado aqui.
        await SendCancellingAsync(executionId, attemptId, ct);
        await _executionManager.CancelAsync(executionId, ct);

        _logger.LogInformation(
            "execution.cancel_requested signaled to running execution {ExecutionId}/{AttemptId}; awaiting ExecuteAsync to unwind.",
            executionId, attemptId);

        return InboxCommandHandlerResult.Processed("cancel_requested_running");
    }

    private async Task SendCancellingAsync(string executionId, string attemptId, CancellationToken ct)
    {
        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionCancelling,
            new { ExecutionId = executionId, ExecutionAttemptId = attemptId },
            executionId: executionId,
            executionAttemptId: attemptId,
            ct: ct);
    }
}
