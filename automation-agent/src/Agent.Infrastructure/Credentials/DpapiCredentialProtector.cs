using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Text;
using Biason.AutomationAgent.Domain.Contracts;

namespace Biason.AutomationAgent.Infrastructure.Credentials;

/// <summary>
/// Proteção de segredos via DPAPI com escopo de máquina.
///
/// O escopo LocalMachine é necessário porque o Agent roda como Windows Service
/// (conta de sistema) e a credencial precisa sobreviver a trocas de usuário.
/// A entropia adicional impede que outro processo na mesma máquina desproteja
/// o blob sem conhecer o segredo da aplicação.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class DpapiCredentialProtector : ICredentialProtector
{
    private static readonly byte[] Entropy =
        Encoding.UTF8.GetBytes("Biason.AutomationAgent/credential-store/v1");

    public string MechanismName => "dpapi-localmachine";

    public bool IsHardened => true;

    public static bool IsSupported => RuntimeInformation.IsOSPlatform(OSPlatform.Windows);

    public byte[] Protect(string plaintext)
    {
        ArgumentNullException.ThrowIfNull(plaintext);
        var bytes = Encoding.UTF8.GetBytes(plaintext);
        try
        {
            return ProtectedData.Protect(bytes, Entropy, DataProtectionScope.LocalMachine);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(bytes);
        }
    }

    public string Unprotect(byte[] protectedBlob)
    {
        ArgumentNullException.ThrowIfNull(protectedBlob);
        var bytes = ProtectedData.Unprotect(protectedBlob, Entropy, DataProtectionScope.LocalMachine);
        try
        {
            return Encoding.UTF8.GetString(bytes);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(bytes);
        }
    }

    public bool TryUnprotect(byte[] protectedBlob, out string? plaintext)
    {
        try
        {
            plaintext = Unprotect(protectedBlob);
            return true;
        }
        catch (Exception ex) when (ex is CryptographicException or ArgumentException)
        {
            // Blob de outra máquina, corrompido, ou perfil DPAPI recriado.
            plaintext = null;
            return false;
        }
    }
}
