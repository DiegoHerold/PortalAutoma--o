using System.Text;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Infrastructure.Credentials;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Credentials;

/// <summary>
/// credential-protection — confirma que o segredo não fica em texto puro.
/// Os testes rodam contra o protetor multiplataforma; o comportamento DPAPI
/// específico do Windows é coberto no teste condicional ao final.
/// </summary>
public sealed class CredentialProtectorTests : IDisposable
{
    private readonly string _tempDir;
    private readonly AesFileKeyCredentialProtector _protector;

    public CredentialProtectorTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"agent-cred-{Guid.NewGuid():N}");
        Directory.CreateDirectory(_tempDir);
        _protector = new AesFileKeyCredentialProtector(Path.Combine(_tempDir, "credential.key"));
    }

    [Fact]
    public void RoundTrip_RecoversOriginalSecret()
    {
        const string secret = "portal-token-super-secreto-123";

        var blob = _protector.Protect(secret);
        var recovered = _protector.Unprotect(blob);

        recovered.Should().Be(secret);
    }

    [Fact]
    public void ProtectedBlob_DoesNotContainPlaintext()
    {
        const string secret = "portal-token-super-secreto-123";

        var blob = _protector.Protect(secret);

        // O segredo não pode aparecer nem como UTF-8 nem como ASCII no blob.
        var asUtf8 = Encoding.UTF8.GetString(blob);
        asUtf8.Should().NotContain(secret);

        var secretBytes = Encoding.UTF8.GetBytes(secret);
        IndexOfSequence(blob, secretBytes).Should().Be(-1,
            "o segredo em texto puro não pode aparecer no blob protegido");
    }

    [Fact]
    public void SameSecret_ProducesDifferentBlobs()
    {
        const string secret = "mesmo-segredo";

        var first = _protector.Protect(secret);
        var second = _protector.Protect(secret);

        // Nonce aleatório por operação: blobs iguais permitiriam correlação.
        first.Should().NotEqual(second);
        _protector.Unprotect(first).Should().Be(secret);
        _protector.Unprotect(second).Should().Be(secret);
    }

    [Fact]
    public void TamperedBlob_FailsToUnprotect()
    {
        var blob = _protector.Protect("segredo");
        blob[^1] ^= 0xFF; // corrompe o ciphertext

        var ok = _protector.TryUnprotect(blob, out var plaintext);

        ok.Should().BeFalse();
        plaintext.Should().BeNull();
    }

    [Fact]
    public void BlobFromDifferentKey_FailsToUnprotect()
    {
        var blob = _protector.Protect("segredo");

        var otherDir = Path.Combine(Path.GetTempPath(), $"agent-cred-{Guid.NewGuid():N}");
        Directory.CreateDirectory(otherDir);
        try
        {
            var other = new AesFileKeyCredentialProtector(Path.Combine(otherDir, "credential.key"));
            other.TryUnprotect(blob, out var plaintext).Should().BeFalse();
            plaintext.Should().BeNull();
        }
        finally
        {
            try { Directory.Delete(otherDir, true); } catch { /* best effort */ }
        }
    }

    [Fact]
    public void TruncatedBlob_FailsGracefully()
    {
        _protector.TryUnprotect(new byte[] { 1, 2, 3 }, out var plaintext).Should().BeFalse();
        plaintext.Should().BeNull();
    }

    [Fact]
    public void AesFallback_IsNotMarkedHardened()
    {
        // O health check depende desta flag para reportar 'degraded' em produção.
        _protector.IsHardened.Should().BeFalse();
        _protector.MechanismName.Should().Be("aes-gcm-filekey");
    }

    [Fact]
    public void KeyFile_IsCreatedOnFirstUse()
    {
        var keyPath = Path.Combine(_tempDir, "credential.key");
        _protector.Protect("x");

        File.Exists(keyPath).Should().BeTrue();
        new FileInfo(keyPath).Length.Should().Be(32, "AES-256 usa chave de 32 bytes");
    }

    [Fact]
    public void CredentialToString_NeverRevealsSecret()
    {
        var credential = new Domain.Agents.AgentCredential
        {
            Type = "client_token",
            Value = "segredo-que-nao-pode-vazar",
            ExpiresAtUtc = DateTime.UtcNow.AddDays(30),
            StoredAtUtc = DateTime.UtcNow
        };

        credential.ToString().Should().NotContain("segredo-que-nao-pode-vazar");
        credential.ToString().Should().Contain("***");
    }

    [Fact]
    public void Dpapi_RoundTrips_OnWindows()
    {
        // DPAPI só existe no Windows; fora dele o teste é um no-op deliberado
        // (evita dependência do pacote SkippableFact só por este caso).
        if (!OperatingSystem.IsWindows())
            return;

        ICredentialProtector dpapi = new DpapiCredentialProtector();
        const string secret = "token-dpapi";

        var blob = dpapi.Protect(secret);
        dpapi.Unprotect(blob).Should().Be(secret);
        dpapi.IsHardened.Should().BeTrue();

        IndexOfSequence(blob, Encoding.UTF8.GetBytes(secret)).Should().Be(-1);
    }

    private static int IndexOfSequence(byte[] haystack, byte[] needle)
    {
        if (needle.Length == 0 || haystack.Length < needle.Length) return -1;

        for (var i = 0; i <= haystack.Length - needle.Length; i++)
        {
            var match = true;
            for (var j = 0; j < needle.Length; j++)
            {
                if (haystack[i + j] != needle[j]) { match = false; break; }
            }
            if (match) return i;
        }
        return -1;
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, recursive: true); } catch { /* best effort */ }
    }
}
