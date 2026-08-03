using System.Security.Cryptography;
using System.Text;

namespace Biason.AutomationAgent.Protocol.Local;

public static class LocalAuthentication
{
    public static string ChallengeResponse(string nonce, string instanceId, int sessionId, int processId)
    {
        var material = $"{nonce}:{instanceId}:{sessionId}:{processId}";
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(material));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}
