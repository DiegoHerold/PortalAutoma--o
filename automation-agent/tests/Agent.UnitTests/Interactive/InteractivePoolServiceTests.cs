using Biason.AutomationAgent.Application.Interactive;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;
using FluentAssertions;
using Microsoft.Extensions.Options;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Interactive;

public sealed class InteractivePoolServiceTests
{
    [Fact]
    public async Task HasSlotAsync_WhenGlobalFull_ReturnsFalse()
    {
        var repo = new FakeAssignments(new[]
        {
            Assignment("exec_1", "att_1", 2, InteractiveExecutionStatus.Running)
        });
        var service = new InteractivePoolService(repo, Options.Create(new InteractivePoolOptions { GlobalSlots = 1, PerSessionSlots = 1 }));

        (await service.HasSlotAsync(3)).Should().BeFalse();
    }

    [Fact]
    public async Task HasSlotAsync_WhenSessionFull_ReturnsFalse()
    {
        var repo = new FakeAssignments(new[]
        {
            Assignment("exec_1", "att_1", 2, InteractiveExecutionStatus.Running)
        });
        var service = new InteractivePoolService(repo, Options.Create(new InteractivePoolOptions { GlobalSlots = 2, PerSessionSlots = 1 }));

        (await service.HasSlotAsync(2)).Should().BeFalse();
    }

    [Fact]
    public async Task HasSlotAsync_WhenUnderLimits_ReturnsTrue()
    {
        var service = new InteractivePoolService(new FakeAssignments(Array.Empty<InteractiveExecutionAssignment>()),
            Options.Create(new InteractivePoolOptions { GlobalSlots = 1, PerSessionSlots = 1 }));

        (await service.HasSlotAsync(2)).Should().BeTrue();
    }

    private static InteractiveExecutionAssignment Assignment(string executionId, string attemptId, int sessionId, InteractiveExecutionStatus status) => new()
    {
        ExecutionId = executionId,
        AttemptId = attemptId,
        SessionId = sessionId,
        SessionRunnerInstanceId = "sr_1",
        Status = status,
        CreatedAtUtc = DateTime.UtcNow
    };

    private sealed class FakeAssignments : IInteractiveExecutionAssignmentRepository
    {
        private readonly IReadOnlyList<InteractiveExecutionAssignment> _items;
        public FakeAssignments(IReadOnlyList<InteractiveExecutionAssignment> items) => _items = items;
        public Task SaveAsync(InteractiveExecutionAssignment assignment, CancellationToken ct = default) => Task.CompletedTask;
        public Task<InteractiveExecutionAssignment?> GetAsync(string executionId, string attemptId, CancellationToken ct = default) => Task.FromResult(_items.FirstOrDefault(i => i.ExecutionId == executionId && i.AttemptId == attemptId));
        public Task<IReadOnlyList<InteractiveExecutionAssignment>> GetActiveAsync(CancellationToken ct = default) => Task.FromResult(_items);
        public Task<IReadOnlyList<InteractiveExecutionAssignment>> GetAllAsync(CancellationToken ct = default) => Task.FromResult(_items);
        public Task<int> CountActiveAsync(CancellationToken ct = default) => Task.FromResult(_items.Count);
        public Task<int> CountActiveBySessionAsync(int sessionId, CancellationToken ct = default) => Task.FromResult(_items.Count(i => i.SessionId == sessionId));
        public Task UpdateStatusAsync(string executionId, string attemptId, InteractiveExecutionStatus status, DateTime nowUtc, string? errorCode = null, string? errorMessage = null, CancellationToken ct = default) => Task.CompletedTask;
        public Task MarkStartedAsync(string executionId, string attemptId, int processId, DateTime nowUtc, CancellationToken ct = default) => Task.CompletedTask;
        public Task MarkCompletedAsync(string executionId, string attemptId, InteractiveExecutionStatus status, int? exitCode, DateTime nowUtc, string? errorCode, string? errorMessage, CancellationToken ct = default) => Task.CompletedTask;
        public Task UpdatePreparedPathsAsync(string executionId, string attemptId, string workspacePath, string runtimePath, string packagePath, CancellationToken ct = default) => Task.CompletedTask;
    }
}
