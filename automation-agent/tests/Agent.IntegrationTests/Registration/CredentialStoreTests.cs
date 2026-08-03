using Biason.AutomationAgent.Domain.Agents;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Microsoft.Data.Sqlite;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Registration;

/// <summary>
/// credential-protection — a credencial nunca pode ficar em texto puro no SQLite.
/// </summary>
public sealed class CredentialStoreTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();
    private const string Secret = "token-do-portal-que-nao-pode-vazar";

    public async Task InitializeAsync() => await _helper.InitializeDatabaseAsync();

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    private static AgentCredential BuildCredential(DateTime? expiresAt = null) => new()
    {
        Type = "client_token",
        Value = Secret,
        ExpiresAtUtc = expiresAt ?? DateTime.UtcNow.AddDays(90),
        StoredAtUtc = DateTime.UtcNow
    };

    [Fact]
    public async Task SaveAndGet_RoundTripsCredential()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        var recovered = await store.GetAsync();

        recovered.Should().NotBeNull();
        recovered!.Value.Should().Be(Secret);
        recovered.Type.Should().Be("client_token");
    }

    [Fact]
    public async Task StoredBlob_DoesNotContainPlaintextSecret()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        // Lê o blob cru direto do banco: o segredo não pode estar lá.
        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT protected_blob FROM agent_credentials_protected WHERE id = 1;";
        var blob = (byte[])(await cmd.ExecuteScalarAsync())!;

        var asText = System.Text.Encoding.UTF8.GetString(blob);
        asText.Should().NotContain(Secret);
    }

    [Fact]
    public async Task MetadataTable_NeverStoresSecret()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        // Varre TODAS as colunas de texto da tabela de metadados.
        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM agent_credentials_metadata WHERE id = 1;";
        using var reader = await cmd.ExecuteReaderAsync();

        (await reader.ReadAsync()).Should().BeTrue();
        for (var i = 0; i < reader.FieldCount; i++)
        {
            if (reader.IsDBNull(i)) continue;
            var value = reader.GetValue(i).ToString();
            value.Should().NotContain(Secret,
                $"a coluna '{reader.GetName(i)}' não pode conter o segredo");
        }
    }

    [Fact]
    public async Task Metadata_ExposesFingerprintNotSecret()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        var metadata = await store.GetMetadataAsync();

        metadata.Should().NotBeNull();
        metadata!.Fingerprint.Should().NotBeNullOrWhiteSpace();
        metadata.Fingerprint.Should().NotContain(Secret);
        metadata.Fingerprint!.Length.Should().Be(16, "fingerprint é SHA-256 truncado a 8 bytes em hex");
        metadata.IsRevoked.Should().BeFalse();
    }

    [Fact]
    public async Task Save_OverwritesPreviousCredential()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());
        await store.SaveAsync(new AgentCredential
        {
            Type = "client_token",
            Value = "segunda-credencial",
            StoredAtUtc = DateTime.UtcNow
        });

        (await store.GetAsync())!.Value.Should().Be("segunda-credencial");

        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM agent_credentials_protected;";
        Convert.ToInt64(await cmd.ExecuteScalarAsync()).Should().Be(1);
    }

    [Fact]
    public async Task Save_ClearsPreviousRevocation()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());
        await store.RevokeAsync("teste");
        (await store.GetMetadataAsync())!.IsRevoked.Should().BeTrue();

        await store.SaveAsync(BuildCredential());

        (await store.GetMetadataAsync())!.IsRevoked.Should().BeFalse();
        (await store.GetAsync()).Should().NotBeNull();
    }

    [Fact]
    public async Task RevokedCredential_IsNotReturned()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        await store.RevokeAsync("revogada pelo Portal");

        (await store.GetAsync()).Should().BeNull();
        (await store.GetMetadataAsync())!.IsRevoked.Should().BeTrue();
    }

    [Fact]
    public async Task CredentialFromAnotherProtector_IsNotReturned()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        // Simula blob de outra máquina: chave diferente para o mesmo mecanismo.
        var otherDir = Path.Combine(Path.GetTempPath(), $"agent-other-{Guid.NewGuid():N}");
        Directory.CreateDirectory(otherDir);
        try
        {
            var foreignProtector = new Biason.AutomationAgent.Infrastructure.Credentials
                .AesFileKeyCredentialProtector(Path.Combine(otherDir, "credential.key"));

            var foreignStore = _helper.CreateCredentialStore(foreignProtector);

            (await foreignStore.GetAsync()).Should().BeNull(
                "um blob que não pode ser desprotegido deve forçar novo registro, não quebrar");
        }
        finally
        {
            try { Directory.Delete(otherDir, true); } catch { /* best effort */ }
        }
    }

    [Fact]
    public async Task Clear_RemovesBothTables()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        await store.ClearAsync();

        (await store.GetAsync()).Should().BeNull();
        (await store.GetMetadataAsync()).Should().BeNull();
    }

    [Fact]
    public async Task TouchLastUsed_UpdatesMetadata()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        (await store.GetMetadataAsync())!.LastUsedAtUtc.Should().BeNull();
        await store.TouchLastUsedAsync();
        (await store.GetMetadataAsync())!.LastUsedAtUtc.Should().NotBeNull();
    }

    [Fact]
    public async Task GetAsync_ReturnsNull_WhenNothingStored()
    {
        var store = _helper.CreateCredentialStore();
        (await store.GetAsync()).Should().BeNull();
        (await store.GetMetadataAsync()).Should().BeNull();
    }

    [Fact]
    public async Task Save_RejectsEmptyCredential()
    {
        var store = _helper.CreateCredentialStore();

        var act = async () => await store.SaveAsync(new AgentCredential { Value = "" });

        await act.Should().ThrowAsync<ArgumentException>();
    }

    [Fact]
    public async Task ProtectedTable_HasSingleRowConstraint()
    {
        var store = _helper.CreateCredentialStore();
        await store.SaveAsync(BuildCredential());

        using var conn = _helper.DbManager.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO agent_credentials_protected (id, protected_blob, protection_mechanism, updated_at_utc)
            VALUES (2, X'00', 'x', '2026-01-01T00:00:00Z');
            """;

        var act = async () => await cmd.ExecuteNonQueryAsync();
        await act.Should().ThrowAsync<SqliteException>("a tabela aceita exatamente uma linha");
    }
}
