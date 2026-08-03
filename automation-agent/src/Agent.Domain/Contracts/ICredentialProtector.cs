namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Protege segredos em repouso. No Windows a implementação usa DPAPI com escopo
/// de máquina; em outras plataformas (testes, CI) usa AES com chave derivada local.
/// </summary>
public interface ICredentialProtector
{
    /// <summary>Nome do mecanismo em uso, para diagnóstico (ex.: "dpapi-localmachine").</summary>
    string MechanismName { get; }

    /// <summary>True quando o mecanismo oferece proteção de nível de sistema operacional.</summary>
    bool IsHardened { get; }

    /// <summary>Protege texto puro, devolvendo blob opaco seguro para persistir.</summary>
    byte[] Protect(string plaintext);

    /// <summary>Reverte <see cref="Protect"/>. Lança se o blob for inválido ou de outra máquina.</summary>
    string Unprotect(byte[] protectedBlob);

    /// <summary>Tenta reverter sem lançar. Usado na inicialização, onde falha é esperada.</summary>
    bool TryUnprotect(byte[] protectedBlob, out string? plaintext);
}
