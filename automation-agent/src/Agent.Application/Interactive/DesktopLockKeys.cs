namespace Biason.AutomationAgent.Application.Interactive;

public static class DesktopLockKeys
{
    public const string WindowsDesktop = "windows_desktop";
    public const string Keyboard = "keyboard";
    public const string Mouse = "mouse";
    public const string ExcelApplication = "excel_application";
    public const string DominioApplication = "dominio_application";

    public static string WindowsSession(int sessionId) => $"windows_session:{sessionId}";

    public static IReadOnlyList<string> Normalize(int sessionId, IEnumerable<string>? requested)
    {
        var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            WindowsDesktop,
            WindowsSession(sessionId),
            Keyboard,
            Mouse
        };

        if (requested is not null)
        {
            foreach (var key in requested.Where(k => !string.IsNullOrWhiteSpace(k)))
                keys.Add(key.Trim());
        }

        return keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase).ToArray();
    }
}
