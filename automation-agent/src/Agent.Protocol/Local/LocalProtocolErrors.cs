namespace Biason.AutomationAgent.Protocol.Local;

public static class LocalProtocolErrors
{
    public const string MalformedJson = "MALFORMED_JSON";
    public const string MessageTooLarge = "MESSAGE_TOO_LARGE";
    public const string UnsupportedProtocolVersion = "UNSUPPORTED_PROTOCOL_VERSION";
    public const string MissingMessageId = "MISSING_MESSAGE_ID";
    public const string MissingMessageType = "MISSING_MESSAGE_TYPE";
    public const string UnknownMessageType = "UNKNOWN_MESSAGE_TYPE";
    public const string MissingSentAt = "MISSING_SENT_AT";
    public const string InvalidToken = "INVALID_TOKEN";
    public const string ExpiredToken = "EXPIRED_TOKEN";
    public const string InvalidChallenge = "INVALID_CHALLENGE";
    public const string ExpiredChallenge = "EXPIRED_CHALLENGE";
    public const string ReplayedChallenge = "REPLAYED_CHALLENGE";
    public const string SessionIdMismatch = "SESSION_ID_MISMATCH";
    public const string InvalidClientPid = "INVALID_CLIENT_PID";
    public const string InvalidRunnerPath = "INVALID_RUNNER_PATH";
    public const string InvalidProcess = "INVALID_RUNNER_PROCESS";
}
