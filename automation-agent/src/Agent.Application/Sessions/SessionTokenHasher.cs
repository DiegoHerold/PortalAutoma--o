using System.Security.Cryptography;
using System.Text;
using Biason.AutomationAgent.Protocol.Local;

namespace Biason.AutomationAgent.Application.Sessions;

internal static class SessionTokenHasher
{
    public static string NewToken(string prefix)
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        return $"{prefix}_{Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')}";
    }

    public static string Fingerprint(string token)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(token));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    public static string ChallengeResponse(string nonce, string instanceId, int sessionId, int processId)
        => LocalAuthentication.ChallengeResponse(nonce, instanceId, sessionId, processId);
}
