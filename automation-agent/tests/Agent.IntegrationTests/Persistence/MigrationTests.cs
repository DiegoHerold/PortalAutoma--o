using Biason.AutomationAgent.Infrastructure.Database;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Persistence;

public class MigrationTests : IDisposable
{
    private readonly string _dbPath;
    private readonly SqliteDatabaseManager _db;

    public MigrationTests()
    {
        _dbPath = Path.Combine(Path.GetTempPath(), $"test_{Guid.NewGuid():N}.db");
        var logger = Substitute.For<ILogger<SqliteDatabaseManager>>();
        _db = new SqliteDatabaseManager(_dbPath, logger);
    }

    [Fact]
    public async Task Initialize_RunsAllMigrations()
    {
        await _db.InitializeAsync();

        // Verify core tables exist
        using var conn = _db.CreateConnection();
        var tables = new List<string>();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;";
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) tables.Add(reader.GetString(0));

        tables.Should().Contain("agent_identity");
        tables.Should().Contain("executions");
        tables.Should().Contain("runtime_artifacts");
        tables.Should().Contain("package_artifacts");
        tables.Should().Contain("execution_attempts");
        tables.Should().Contain("execution_events");
        tables.Should().Contain("resource_reservations");
    }

    [Fact]
    public async Task Initialize_IsIdempotent()
    {
        await _db.InitializeAsync();
        await _db.InitializeAsync(); // Should not throw

        var integrity = await _db.VerifyIntegrityAsync();
        integrity.Should().BeTrue();
    }

    public void Dispose()
    {
        try { File.Delete(_dbPath); } catch { }
        try { File.Delete(_dbPath + "-wal"); } catch { }
        try { File.Delete(_dbPath + "-shm"); } catch { }
    }
}
