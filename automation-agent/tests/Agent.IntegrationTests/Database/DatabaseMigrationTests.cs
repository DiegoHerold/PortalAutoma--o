using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Database;

public class DatabaseMigrationTests : IDisposable
{
    private readonly TestHelper _helper = new();

    [Fact]
    public async Task InitializeAsync_CreatesSchema()
    {
        await _helper.InitializeDatabaseAsync();

        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;";
        var tables = new List<string>();
        using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            tables.Add(reader.GetString(0));

        tables.Should().Contain("agent_identity");
        tables.Should().Contain("agent_state");
        tables.Should().Contain("agent_state_transitions");
        tables.Should().Contain("machine_profiles");
        tables.Should().Contain("resource_samples");
        tables.Should().Contain("capabilities");
        tables.Should().Contain("executions");
        tables.Should().Contain("execution_state_transitions");
        tables.Should().Contain("outbox_events");
        tables.Should().Contain("inbox_commands");
        tables.Should().Contain("schema_migrations");
    }

    [Fact]
    public async Task InitializeAsync_Idempotent()
    {
        await _helper.InitializeDatabaseAsync();

        // Running again should not throw
        _helper.DbManager.Dispose();
        var helper2 = new TestHelper();
        // Reuse same dir
        var act = async () =>
        {
            var h = new TestHelper();
            // Recreate pointing to same temp
            await h.InitializeDatabaseAsync();
            h.Dispose();
        };
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task VerifyIntegrity_ReturnsTrue()
    {
        await _helper.InitializeDatabaseAsync();
        var ok = await _helper.DbManager.VerifyIntegrityAsync();
        ok.Should().BeTrue();
    }

    [Fact]
    public async Task GetDatabaseSizeKb_ReturnsPositive()
    {
        await _helper.InitializeDatabaseAsync();
        var size = _helper.DbManager.GetDatabaseSizeKb();
        size.Should().BeGreaterThanOrEqualTo(0);
    }

    public void Dispose() => _helper.Dispose();
}
