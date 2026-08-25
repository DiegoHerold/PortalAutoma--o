using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;

namespace Biason.AutomationAgent.Certification.Core.Processes;

/// <summary>
/// Launches a process with <c>CREATE_NEW_PROCESS_GROUP</c> so it can later
/// be sent a real <c>CTRL_BREAK_EVENT</c> for graceful shutdown, instead of
/// being force-killed every time (docs/certification-harness.md item 13
/// "Shutdown limpo" / item 14 "CertificationProcessSupervisor").
///
/// .NET's own <c>PosixSignalRegistration</c> (used by the Generic Host to
/// react to SIGINT/SIGTERM) is implemented on Windows via
/// <c>SetConsoleCtrlHandler</c>, which is exactly what
/// <c>GenerateConsoleCtrlEvent</c> triggers — so a real Agent.Service
/// process (an ASP.NET Core Generic Host) reacts to CTRL_BREAK the same way
/// it would react to SIGTERM on Linux: <c>IHostApplicationLifetime</c> runs
/// its normal shutdown sequence.
///
/// <c>GenerateConsoleCtrlEvent</c> can only target a specific, non-zero
/// process group id (not just any PID) — that requires the target to have
/// been created with <c>CREATE_NEW_PROCESS_GROUP</c>, at which point its
/// own process id becomes its process group id. That is the entire reason
/// this class exists instead of relying on <see cref="System.Diagnostics.Process.Start"/>,
/// which does not expose Windows process creation flags.
///
/// This is the one place in the certification harness that talks to Win32
/// directly. Everything else uses <see cref="System.Diagnostics.Process"/>.
/// </summary>
[SupportedOSPlatform("windows")]
public static class NativeProcess
{
    private const uint CREATE_NEW_PROCESS_GROUP = 0x00000200;
    private const uint CREATE_NO_WINDOW = 0x08000000;
    private const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
    private const int STARTF_USESTDHANDLES = 0x00000100;
    private const uint CTRL_BREAK_EVENT = 1;

    [StructLayout(LayoutKind.Sequential)]
    private struct SECURITY_ATTRIBUTES
    {
        public int nLength;
        public IntPtr lpSecurityDescriptor;
        public int bInheritHandle;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct STARTUPINFO
    {
        public int cb;
        public string? lpReserved;
        public string? lpDesktop;
        public string? lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public int dwProcessId;
        public int dwThreadId;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcess(
        string? lpApplicationName,
        StringBuilder lpCommandLine,
        ref SECURITY_ATTRIBUTES lpProcessAttributes,
        ref SECURITY_ATTRIBUTES lpThreadAttributes,
        bool bInheritHandles,
        uint dwCreationFlags,
        IntPtr lpEnvironment,
        string? lpCurrentDirectory,
        ref STARTUPINFO lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GenerateConsoleCtrlEvent(uint dwCtrlEvent, uint dwProcessGroupId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetStdHandle(int nStdHandle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetHandleInformation(IntPtr hObject, uint dwMask, uint dwFlags);

    private const int STD_OUTPUT_HANDLE = -11;
    private const int STD_ERROR_HANDLE = -12;
    private const uint HANDLE_FLAG_INHERIT = 0x00000001;

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateFile(
        string lpFileName,
        uint dwDesiredAccess,
        uint dwShareMode,
        ref SECURITY_ATTRIBUTES lpSecurityAttributes,
        uint dwCreationDisposition,
        uint dwFlagsAndAttributes,
        IntPtr hTemplateFile);

    private const uint GENERIC_WRITE = 0x40000000;
    private const uint FILE_SHARE_READ = 0x00000001;
    private const uint FILE_SHARE_WRITE = 0x00000002;
    private const uint CREATE_ALWAYS = 2;
    private const uint FILE_ATTRIBUTE_NORMAL = 0x80;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new(-1);

    public sealed record LaunchedProcess(int ProcessId, IntPtr ProcessHandle);

    /// <summary>
    /// Starts a process in its own console process group, with stdout/stderr
    /// redirected to the given file paths. The caller is responsible for
    /// eventually calling <see cref="System.Diagnostics.Process.GetProcessById(int)"/>
    /// with <see cref="LaunchedProcess.ProcessId"/> for waiting, and for
    /// closing <see cref="LaunchedProcess.ProcessHandle"/> via
    /// <see cref="CloseProcessHandle"/> once done with it.
    /// </summary>
    public static LaunchedProcess Start(
        string fileName,
        string arguments,
        string workingDirectory,
        IReadOnlyDictionary<string, string?> environment,
        string stdoutPath,
        string stderrPath)
    {
        // Regressao: CreateProcess abaixo usa bInheritHandles=true (necessario
        // para repassar os dois handles de arquivo hStdOutput/hStdError deste
        // metodo para o processo filho). Isso NAO inherita so os dois handles
        // explicitos - ele duplica TODO handle marcavel-como-herdavel que este
        // processo (a CLI "certification") ja tem aberto, inclusive seu
        // proprio stdout/stderr. Quando "certification start/stop" e chamado
        // de dentro de um wrapper que captura a saida (ex.: PowerShell com
        // "2>&1 | ForEach-Object", usado para transmitir o log em tempo real),
        // esse stdout/stderr sao handles de PIPE anonimo herdaveis. O
        // Agent.Service (um servico de longa duracao, criado aqui como um
        // "grandchild" do wrapper) acaba herdando uma copia extra desses
        // handles de pipe e nunca os fecha - entao o lado de leitura do
        // wrapper (ForEach-Object/Out-String) NUNCA ve EOF, mesmo depois do
        // processo "certification start/stop" em si ja ter terminado (exit
        // code 0). O script trava para sempre esperando o pipe fechar.
        // Corrigido removendo a herdabilidade dos handles std do PROCESSO
        // ATUAL antes do CreateProcess - assim bInheritHandles=true so
        // repassa os dois handles de arquivo que passamos explicitamente via
        // STARTUPINFO, e nao os handles de pipe do chamador.
        ClearOwnStdHandleInheritance();

        var inheritableSecurity = new SECURITY_ATTRIBUTES
        {
            nLength = Marshal.SizeOf<SECURITY_ATTRIBUTES>(),
            lpSecurityDescriptor = IntPtr.Zero,
            bInheritHandle = 1
        };

        var stdoutHandle = CreateInheritableFile(stdoutPath, ref inheritableSecurity);
        var stderrHandle = CreateInheritableFile(stderrPath, ref inheritableSecurity);

        try
        {
            var startupInfo = new STARTUPINFO
            {
                dwFlags = STARTF_USESTDHANDLES,
                hStdOutput = stdoutHandle,
                hStdError = stderrHandle,
                hStdInput = IntPtr.Zero
            };
            startupInfo.cb = Marshal.SizeOf<STARTUPINFO>();

            var processAttributes = new SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf<SECURITY_ATTRIBUTES>() };
            var threadAttributes = new SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf<SECURITY_ATTRIBUTES>() };

            var commandLine = new StringBuilder($"\"{fileName}\" {arguments}");
            var environmentBlock = BuildEnvironmentBlock(environment);
            var envHandle = GCHandle.Alloc(environmentBlock, GCHandleType.Pinned);

            try
            {
                var created = CreateProcess(
                    null,
                    commandLine,
                    ref processAttributes,
                    ref threadAttributes,
                    bInheritHandles: true,
                    dwCreationFlags: CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
                    lpEnvironment: envHandle.AddrOfPinnedObject(),
                    lpCurrentDirectory: workingDirectory,
                    lpStartupInfo: ref startupInfo,
                    lpProcessInformation: out var processInfo);

                if (!created)
                {
                    var error = Marshal.GetLastWin32Error();
                    throw new Win32Exception(error, $"CreateProcess failed for '{fileName}' (Win32 error {error}).");
                }

                if (processInfo.hThread != IntPtr.Zero)
                    CloseHandle(processInfo.hThread);

                return new LaunchedProcess(processInfo.dwProcessId, processInfo.hProcess);
            }
            finally
            {
                envHandle.Free();
            }
        }
        finally
        {
            if (stdoutHandle != IntPtr.Zero) CloseHandle(stdoutHandle);
            if (stderrHandle != IntPtr.Zero) CloseHandle(stderrHandle);
        }
    }

    /// <summary>
    /// Strips HANDLE_FLAG_INHERIT from this process's own stdout/stderr
    /// handles so the CreateProcess call in <see cref="Start"/> (which needs
    /// bInheritHandles=true to hand the two explicit log-file handles to the
    /// child) does not also duplicate this process's own std handles into
    /// the child. Best-effort: a real console (not a redirected pipe) either
    /// fails or is a no-op here, and either way is safe to ignore - only a
    /// redirected/piped caller has anything to fix.
    /// </summary>
    private static void ClearOwnStdHandleInheritance()
    {
        foreach (var stdHandleId in new[] { STD_OUTPUT_HANDLE, STD_ERROR_HANDLE })
        {
            var handle = GetStdHandle(stdHandleId);
            if (handle != IntPtr.Zero && handle != INVALID_HANDLE_VALUE)
                SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0);
        }
    }

    public static void CloseProcessHandle(IntPtr handle)
    {
        if (handle != IntPtr.Zero)
            CloseHandle(handle);
    }

    /// <summary>
    /// Sends CTRL_BREAK_EVENT to the process group led by <paramref name="processId"/>.
    /// Only works for processes started via <see cref="Start"/> (i.e. created
    /// with CREATE_NEW_PROCESS_GROUP). Returns false on failure instead of
    /// throwing — the caller must fall back to a forced kill and record that
    /// (docs/certification-harness.md item 13).
    /// </summary>
    public static bool TrySendGracefulStop(int processId)
    {
        try
        {
            return GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, (uint)processId);
        }
        catch
        {
            return false;
        }
    }

    private static IntPtr CreateInheritableFile(string path, ref SECURITY_ATTRIBUTES security)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? ".");
        var handle = CreateFile(
            path,
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            ref security,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            IntPtr.Zero);

        if (handle == INVALID_HANDLE_VALUE)
        {
            var error = Marshal.GetLastWin32Error();
            throw new Win32Exception(error, $"CreateFile failed for '{path}' (Win32 error {error}).");
        }

        return handle;
    }

    private static byte[] BuildEnvironmentBlock(IReadOnlyDictionary<string, string?> overrides)
    {
        var merged = new SortedDictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (System.Collections.DictionaryEntry entry in Environment.GetEnvironmentVariables())
        {
            if (entry.Key is string key && entry.Value is string value)
                merged[key] = value;
        }

        foreach (var (key, value) in overrides)
        {
            if (value is null)
                merged.Remove(key);
            else
                merged[key] = value;
        }

        var builder = new StringBuilder();
        foreach (var (key, value) in merged)
        {
            builder.Append(key).Append('=').Append(value).Append('\0');
        }
        builder.Append('\0');

        return Encoding.Unicode.GetBytes(builder.ToString());
    }
}
