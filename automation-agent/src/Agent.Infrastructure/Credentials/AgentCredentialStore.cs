using System.Security.Cryptography;
using System.Text;
using Biason.AutomationAgent.Domain.Agents;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Credentials;

/// <summary>
/// Persiste a credencial do Agent em duas tabelas separadas:
/// o blob protegido e os metadados não sensíveis. Nenhum caminho de código
/// escreve o segredo em texto puro no SQLite ou em log.
/// </summary>
public sealed class AgentCredentialStore : IAgentCredentialStore
{
    private readonly SqliteDatabaseManager _db;
    private readonly ICredentialProtector _protector;
    private readonly IClock _clock;
    private readonly ILogger<AgentCredentialStore> _logger;

    public AgentCredentialStore(
        SqliteDatabaseManager db,
        ICredentialProtector protector,
        IClock clock,
        ILogger<AgentCredentialStore> logger)
    {
        _db = db;
        _protector = protector;
        _clock = clock;
        _logger = logger;
    }

    public async Task SaveAsync(AgentCredential credential, CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(credential);
        if (string.IsNullOrWhiteSpace(credential.Value))
            throw new ArgumentException("Credencial sem valor.", nameof(credential));

        var blob = _protector.Protect(credential.Value);
        var fingerprint = ComputeFingerprint(credential.Value);
        var now = _clock.UtcNow;

        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();

        using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = tx;
            cmd.CommandText = """
                INSERT INTO agent_credentials_protected (id, protected_blob, protection_mechanism, updated_at_utc)
                VALUES (1, $blob, $mech, $now)
                ON CONFLICT(id) DO UPDATE SET
                    protected_blob = excluded.protected_blob,
                    protection_mechanism = excluded.protection_mechanism,
                    updated_at_utc = excluded.updated_at_utc;
                """;
            cmd.Parameters.AddWithValue("$blob", blob);
            cmd.Parameters.AddWithValue("$mech", _protector.MechanismName);
            cmd.Parameters.AddWithValue("$now", now.ToString("o"));
            await cmd.ExecuteNonQueryAsync(ct);
        }

        using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = tx;
            cmd.CommandText = """
                INSERT INTO agent_credentials_metadata
                    (id, credential_type, fingerprint, protection_mechanism, stored_at_utc, expires_at_utc,
                     last_used_at_utc, revoked_at_utc, revocation_reason)
                VALUES (1, $type, $fp, $mech, $now, $exp, NULL, NULL, NULL)
                ON CONFLICT(id) DO UPDATE SET
                    credential_type = excluded.credential_type,
                    fingerprint = excluded.fingerprint,
                    protection_mechanism = excluded.protection_mechanism,
                    stored_at_utc = excluded.stored_at_utc,
                    expires_at_utc = excluded.expires_at_utc,
                    last_used_at_utc = NULL,
                    revoked_at_utc = NULL,
                    revocation_reason = NULL;
                """;
            cmd.Parameters.AddWithValue("$type", credential.Type);
            cmd.Parameters.AddWithValue("$fp", fingerprint);
            cmd.Parameters.AddWithValue("$mech", _protector.MechanismName);
            cmd.Parameters.AddWithValue("$now", now.ToString("o"));
            cmd.Parameters.AddWithValue("$exp", (object?)credential.ExpiresAtUtc?.ToString("o") ?? DBNull.Value);
            await cmd.ExecuteNonQueryAsync(ct);
        }

        tx.Commit();

        // Nota deliberada: o log registra o mecanismo e o fingerprint, nunca o segredo.
        _logger.LogInformation(
            "Credencial do Agent armazenada (mecanismo={Mechanism}, fingerprint={Fingerprint}, expira={ExpiresAt})",
            _protector.MechanismName, fingerprint, credential.ExpiresAtUtc);
    }

    public async Task<AgentCredential?> GetAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();

        byte[]? blob = null;
        string? mechanism = null;

        using (var cmd = conn.CreateCommand())
        {
            cmd.CommandText = "SELECT protected_blob, protection_mechanism FROM agent_credentials_protected WHERE id = 1;";
            using var reader = await cmd.ExecuteReaderAsync(ct);
            if (await reader.ReadAsync(ct))
            {
                blob = (byte[])reader["protected_blob"];
                mechanism = reader.GetString(1);
            }
        }

        if (blob is null)
            return null;

        if (!string.Equals(mechanism, _protector.MechanismName, StringComparison.Ordinal))
        {
            _logger.LogWarning(
                "Credencial protegida por mecanismo '{Stored}' mas o ativo é '{Active}'. Novo registro será necessário.",
                mechanism, _protector.MechanismName);
            return null;
        }

        if (!_protector.TryUnprotect(blob, out var plaintext) || plaintext is null)
        {
            _logger.LogWarning(
                "Não foi possível desproteger a credencial (blob de outra máquina ou corrompido). Novo registro será necessário.");
            return null;
        }

        var metadata = await GetMetadataAsync(ct);
        if (metadata?.IsRevoked == true)
        {
            _logger.LogWarning("Credencial revogada em {RevokedAt}.", metadata.RevokedAtUtc);
            return null;
        }

        return new AgentCredential
        {
            Type = metadata?.Type ?? "client_token",
            Value = plaintext,
            ExpiresAtUtc = metadata?.ExpiresAtUtc,
            StoredAtUtc = metadata?.StoredAtUtc ?? _clock.UtcNow
        };
    }

    public async Task<AgentCredentialMetadata?> GetMetadataAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT credential_type, fingerprint, stored_at_utc, expires_at_utc,
                   last_used_at_utc, revoked_at_utc
            FROM agent_credentials_metadata WHERE id = 1;
            """;

        using var reader = await cmd.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct))
            return null;

        return new AgentCredentialMetadata
        {
            Type = reader.GetString(0),
            Fingerprint = reader.IsDBNull(1) ? null : reader.GetString(1),
            StoredAtUtc = DateTime.Parse(reader.GetString(2)).ToUniversalTime(),
            ExpiresAtUtc = reader.IsDBNull(3) ? null : DateTime.Parse(reader.GetString(3)).ToUniversalTime(),
            LastUsedAtUtc = reader.IsDBNull(4) ? null : DateTime.Parse(reader.GetString(4)).ToUniversalTime(),
            RevokedAtUtc = reader.IsDBNull(5) ? null : DateTime.Parse(reader.GetString(5)).ToUniversalTime()
        };
    }

    public async Task RevokeAsync(string reason, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE agent_credentials_metadata
            SET revoked_at_utc = $now, revocation_reason = $reason
            WHERE id = 1;
            """;
        cmd.Parameters.AddWithValue("$now", _clock.UtcNow.ToString("o"));
        cmd.Parameters.AddWithValue("$reason", reason);
        await cmd.ExecuteNonQueryAsync(ct);

        _logger.LogWarning("Credencial do Agent revogada: {Reason}", reason);
    }

    public async Task TouchLastUsedAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE agent_credentials_metadata SET last_used_at_utc = $now WHERE id = 1;";
        cmd.Parameters.AddWithValue("$now", _clock.UtcNow.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task ClearAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();

        foreach (var sql in new[]
                 {
                     "DELETE FROM agent_credentials_protected WHERE id = 1;",
                     "DELETE FROM agent_credentials_metadata WHERE id = 1;"
                 })
        {
            using var cmd = conn.CreateCommand();
            cmd.Transaction = tx;
            cmd.CommandText = sql;
            await cmd.ExecuteNonQueryAsync(ct);
        }

        tx.Commit();
        _logger.LogInformation("Credencial do Agent removida do armazenamento local.");
    }

    /// <summary>
    /// Fingerprint curto para correlação em logs e diagnóstico.
    /// Irreversível: SHA-256 truncado, sem o segredo.
    /// </summary>
    private static string ComputeFingerprint(string secret)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(secret));
        return Convert.ToHexString(hash.AsSpan(0, 8)).ToLowerInvariant();
    }
}
