using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Credentials;

/// <summary>
/// Escolhe o mecanismo de proteção adequado à plataforma.
///
/// A seleção fica isolada aqui para que o restante do código nunca precise
/// de checagens de plataforma — e para que a anotação [SupportedOSPlatform]
/// do protetor DPAPI não vaze avisos de análise para os pontos de uso.
/// </summary>
public static class CredentialProtectorFactory
{
    public static ICredentialProtector Create(IDirectoryResolver directories, ILoggerFactory loggerFactory)
    {
        var logger = loggerFactory.CreateLogger(typeof(CredentialProtectorFactory));

        if (OperatingSystem.IsWindows())
        {
            logger.LogInformation("Proteção de credenciais: DPAPI (escopo de máquina).");
            return new DpapiCredentialProtector();
        }

        // Fora do Windows (testes, CI) não há DPAPI. Usamos AES-GCM com chave em
        // arquivo restrito. É explicitamente menos robusto: IsHardened = false,
        // e o health check de registro reporta 'degraded' se isso ocorrer em produção.
        var keyPath = Path.Combine(directories.ConfigPath, "credential.key");
        logger.LogWarning(
            "DPAPI indisponível nesta plataforma; usando AES-GCM com chave em arquivo ({Path}). " +
            "Adequado apenas a desenvolvimento e testes.", keyPath);

        return new AesFileKeyCredentialProtector(keyPath);
    }
}
