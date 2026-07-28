using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Infrastructure.Database;

public sealed class SqliteDatabaseManager : IDatabaseManager, IDisposable
{
    private readonly string _connectionString;
    private readonly ILogger<SqliteDatabaseManager> _logger;
    private readonly DatabaseOptions _options;
    private readonly IDirectoryResolver _dirs;
    private SqliteConnection? _keepAlive;

    public SqliteDatabaseManager(
        IDirectoryResolver dirs,
        IOptions<DatabaseOptions> options,
        ILogger<SqliteDatabaseManager> logger)
    {
        _dirs = dirs;
        _options = options.Value;
        _logger = logger;
        _connectionString = $"Data Source={dirs.DatabaseFilePath};Cache=Shared";
    }

    public SqliteConnection CreateConnection()
    {
        var conn = new SqliteConnection(_connectionString);
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"PRAGMA busy_timeout = {_options.BusyTimeoutMs};";
        cmd.ExecuteNonQuery();
        return conn;
    }

    public async Task InitializeAsync(CancellationToken ct = default)
    {
        _logger.LogInformation("Initializing SQLite database at {Path}", _dirs.DatabaseFilePath);

        _keepAlive = new SqliteConnection(_connectionString);
        await _keepAlive.OpenAsync(ct);

        using var cmd = _keepAlive.CreateCommand();
        cmd.CommandText = $"""
            PRAGMA journal_mode = {_options.JournalMode};
            PRAGMA busy_timeout = {_options.BusyTimeoutMs};
            PRAGMA synchronous = NORMAL;
            PRAGMA foreign_keys = ON;
            PRAGMA temp_store = MEMORY;
            """;
        await cmd.ExecuteNonQueryAsync(ct);

        await RunMigrationsAsync(ct);

        _logger.LogInformation("SQLite database initialized successfully");
    }

    public async Task<bool> VerifyIntegrityAsync(CancellationToken ct = default)
    {
        try
        {
            using var conn = CreateConnection();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "PRAGMA integrity_check;";
            var result = await cmd.ExecuteScalarAsync(ct);
            var ok = result?.ToString() == "ok";
            if (!ok)
                _logger.LogWarning("Database integrity check failed: {Result}", result);
            return ok;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Database integrity check error");
            return false;
        }
    }

    public long GetDatabaseSizeKb()
    {
        try
        {
            var fi = new FileInfo(_dirs.DatabaseFilePath);
            return fi.Exists ? fi.Length / 1024 : 0;
        }
        catch
        {
            return 0;
        }
    }

    private async Task RunMigrationsAsync(CancellationToken ct)
    {
        if (_keepAlive is null) throw new InvalidOperationException("Database not open");

        using var cmd = _keepAlive.CreateCommand();
        cmd.CommandText = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """;
        await cmd.ExecuteNonQueryAsync(ct);

        var applied = new HashSet<int>();
        cmd.CommandText = "SELECT version FROM schema_migrations;";
        using (var reader = await cmd.ExecuteReaderAsync(ct))
        {
            while (await reader.ReadAsync(ct))
                applied.Add(reader.GetInt32(0));
        }

        foreach (var migration in Migrations.All.OrderBy(m => m.Version))
        {
            if (applied.Contains(migration.Version))
                continue;

            _logger.LogInformation("Applying migration {Version}: {Name}", migration.Version, migration.Name);

            using var tx = _keepAlive.BeginTransaction();
            try
            {
                var migCmd = _keepAlive.CreateCommand();
                migCmd.Transaction = tx;
                migCmd.CommandText = migration.Sql;
                await migCmd.ExecuteNonQueryAsync(ct);

                var recordCmd = _keepAlive.CreateCommand();
                recordCmd.Transaction = tx;
                recordCmd.CommandText = "INSERT INTO schema_migrations (version, name) VALUES ($v, $n);";
                recordCmd.Parameters.AddWithValue("$v", migration.Version);
                recordCmd.Parameters.AddWithValue("$n", migration.Name);
                await recordCmd.ExecuteNonQueryAsync(ct);

                tx.Commit();
                _logger.LogInformation("Migration {Version} applied successfully", migration.Version);
            }
            catch
            {
                tx.Rollback();
                throw;
            }
        }
    }

    public void Dispose()
    {
        _keepAlive?.Dispose();
    }
}
