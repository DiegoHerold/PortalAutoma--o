using System.Text.RegularExpressions;

namespace Biason.AutomationAgent.Certification.Core.Reporting;

/// <summary>
/// Last-resort guard against docs/certification-harness.md item 78: the
/// report must never contain a bearer token, secret, signed upload URL,
/// connection string, or password. This does not replace being careful
/// about what gets assigned into <see cref="CertificationReport"/> fields —
/// it just fails loudly if something slipped through, instead of silently
/// writing a report with a leaked credential.
/// </summary>
public static partial class SecretScan
{
    [GeneratedRegex(@"(?i)(bearer\s+[a-z0-9._\-]{16,}|password\s*[:=]\s*\S+|connectionstring|connection_string|X-Amz-Signature|Signature=)")]
    private static partial Regex SuspiciousPatterns();

    public static void ThrowIfLooksLikeSecret(string json)
    {
        var match = SuspiciousPatterns().Match(json);
        if (match.Success)
        {
            throw new InvalidOperationException(
                $"Refusing to write certification report: content matched a secret-shaped pattern near '{Truncate(match.Value)}'. " +
                "Check what was assigned into CertificationReport before saving.");
        }
    }

    private static string Truncate(string value) => value.Length <= 24 ? value : value[..24] + "...";
}
