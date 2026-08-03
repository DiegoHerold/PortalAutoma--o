using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Biason.AutomationAgent.Protocol.Serialization;

namespace Biason.AutomationAgent.Protocol.Local;

public static class LocalExecutionToken
{
    public static string Issue(
        string signingSecret,
        string executionId,
        string attemptId,
        int sessionId,
        string sessionRunnerInstanceId,
        DateTime expiresAtUtc)
    {
        var payload = new TokenPayload
        {
            ExecutionId = executionId,
            AttemptId = attemptId,
            SessionId = sessionId,
            SessionRunnerInstanceId = sessionRunnerInstanceId,
            ExpiresAtUtc = expiresAtUtc,
            Nonce = Guid.NewGuid().ToString("N")
        };

        var payloadJson = ProtocolJson.Serialize(payload);
        var payloadB64 = Base64Url(Encoding.UTF8.GetBytes(payloadJson));
        var signature = Sign(signingSecret, payloadB64);
        return $"{payloadB64}.{signature}";
    }

    public static bool TryValidate(
        string token,
        string signingSecret,
        string executionId,
        string attemptId,
        int sessionId,
        string sessionRunnerInstanceId,
        DateTime nowUtc,
        out string? errorCode)
    {
        errorCode = null;
        var parts = token.Split('.', 2);
        if (parts.Length != 2)
        {
            errorCode = LocalProtocolErrors.InvalidToken;
            return false;
        }

        var expected = Sign(signingSecret, parts[0]);
        if (!CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(expected), Encoding.UTF8.GetBytes(parts[1])))
        {
            errorCode = "INTERACTIVE_EXECUTION_TOKEN_INVALID";
            return false;
        }

        TokenPayload? payload;
        try
        {
            payload = ProtocolJson.Deserialize<TokenPayload>(Encoding.UTF8.GetString(Base64UrlDecode(parts[0])));
        }
        catch
        {
            errorCode = "INTERACTIVE_EXECUTION_TOKEN_INVALID";
            return false;
        }

        if (payload is null)
        {
            errorCode = "INTERACTIVE_EXECUTION_TOKEN_INVALID";
            return false;
        }

        if (payload.ExpiresAtUtc <= nowUtc)
        {
            errorCode = "INTERACTIVE_EXECUTION_TOKEN_EXPIRED";
            return false;
        }

        var ok = payload.ExecutionId == executionId &&
                 payload.AttemptId == attemptId &&
                 payload.SessionId == sessionId &&
                 payload.SessionRunnerInstanceId == sessionRunnerInstanceId;

        if (!ok)
            errorCode = "INTERACTIVE_EXECUTION_TOKEN_INVALID";

        return ok;
    }

    private static string Sign(string secret, string payloadB64)
    {
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        return Base64Url(hmac.ComputeHash(Encoding.UTF8.GetBytes(payloadB64)));
    }

    private static string Base64Url(byte[] bytes) =>
        Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');

    private static byte[] Base64UrlDecode(string text)
    {
        var padded = text.Replace('-', '+').Replace('_', '/');
        padded = padded.PadRight(padded.Length + ((4 - padded.Length % 4) % 4), '=');
        return Convert.FromBase64String(padded);
    }

    private sealed class TokenPayload
    {
        public string ExecutionId { get; init; } = default!;
        public string AttemptId { get; init; } = default!;
        public int SessionId { get; init; }
        public string SessionRunnerInstanceId { get; init; } = default!;
        public DateTime ExpiresAtUtc { get; init; }
        public string Nonce { get; init; } = default!;
    }
}
