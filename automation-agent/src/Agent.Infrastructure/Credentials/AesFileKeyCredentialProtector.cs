using System.Security.Cryptography;
using System.Text;
using Biason.AutomationAgent.Domain.Contracts;

namespace Biason.AutomationAgent.Infrastructure.Credentials;

/// <summary>
/// Fallback multiplataforma usado apenas quando DPAPI não está disponível
/// (testes, CI Linux). Cifra com AES-256-GCM usando chave gerada uma única vez
/// e guardada em arquivo com permissões restritas.
///
/// Menos robusto que DPAPI — um processo com acesso ao arquivo de chave consegue
/// desproteger. Por isso <see cref="IsHardened"/> é false, e o health check
/// de registro reporta <c>degraded</c> quando este mecanismo está em uso em produção.
/// </summary>
public sealed class AesFileKeyCredentialProtector : ICredentialProtector
{
    private const int KeySizeBytes = 32;   // AES-256
    private const int NonceSizeBytes = 12; // GCM padrão
    private const int TagSizeBytes = 16;

    private static readonly byte[] AssociatedData =
        Encoding.UTF8.GetBytes("Biason.AutomationAgent/credential-store/v1");

    private readonly string _keyFilePath;
    private readonly Lazy<byte[]> _key;

    public AesFileKeyCredentialProtector(string keyFilePath)
    {
        _keyFilePath = keyFilePath;
        _key = new Lazy<byte[]>(LoadOrCreateKey, LazyThreadSafetyMode.ExecutionAndPublication);
    }

    public string MechanismName => "aes-gcm-filekey";

    public bool IsHardened => false;

    public byte[] Protect(string plaintext)
    {
        ArgumentNullException.ThrowIfNull(plaintext);

        var plainBytes = Encoding.UTF8.GetBytes(plaintext);
        var nonce = RandomNumberGenerator.GetBytes(NonceSizeBytes);
        var cipher = new byte[plainBytes.Length];
        var tag = new byte[TagSizeBytes];

        try
        {
            using var aes = new AesGcm(_key.Value, TagSizeBytes);
            aes.Encrypt(nonce, plainBytes, cipher, tag, AssociatedData);

            // Layout: [nonce][tag][ciphertext]
            var output = new byte[NonceSizeBytes + TagSizeBytes + cipher.Length];
            nonce.CopyTo(output, 0);
            tag.CopyTo(output, NonceSizeBytes);
            cipher.CopyTo(output, NonceSizeBytes + TagSizeBytes);
            return output;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plainBytes);
        }
    }

    public string Unprotect(byte[] protectedBlob)
    {
        ArgumentNullException.ThrowIfNull(protectedBlob);

        if (protectedBlob.Length < NonceSizeBytes + TagSizeBytes)
            throw new CryptographicException("Blob protegido é curto demais para ser válido.");

        var nonce = protectedBlob.AsSpan(0, NonceSizeBytes);
        var tag = protectedBlob.AsSpan(NonceSizeBytes, TagSizeBytes);
        var cipher = protectedBlob.AsSpan(NonceSizeBytes + TagSizeBytes);
        var plainBytes = new byte[cipher.Length];

        try
        {
            using var aes = new AesGcm(_key.Value, TagSizeBytes);
            aes.Decrypt(nonce, cipher, tag, plainBytes, AssociatedData);
            return Encoding.UTF8.GetString(plainBytes);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plainBytes);
        }
    }

    public bool TryUnprotect(byte[] protectedBlob, out string? plaintext)
    {
        try
        {
            plaintext = Unprotect(protectedBlob);
            return true;
        }
        catch (Exception ex) when (ex is CryptographicException or ArgumentException or IOException)
        {
            plaintext = null;
            return false;
        }
    }

    private byte[] LoadOrCreateKey()
    {
        var dir = Path.GetDirectoryName(_keyFilePath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        if (File.Exists(_keyFilePath))
        {
            var existing = File.ReadAllBytes(_keyFilePath);
            if (existing.Length == KeySizeBytes)
                return existing;

            // Chave corrompida: regenerar invalida credenciais antigas de propósito,
            // forçando novo registro em vez de operar com material duvidoso.
            CryptographicOperations.ZeroMemory(existing);
        }

        var key = RandomNumberGenerator.GetBytes(KeySizeBytes);
        File.WriteAllBytes(_keyFilePath, key);
        RestrictFilePermissions(_keyFilePath);
        return key;
    }

    private static void RestrictFilePermissions(string path)
    {
        if (OperatingSystem.IsWindows())
            return; // No Windows este fallback não é usado; DPAPI cobre o caso.

        try
        {
            File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or PlatformNotSupportedException)
        {
            // Sistema de arquivos sem suporte a modo Unix — segue com o padrão do FS.
        }
    }
}
