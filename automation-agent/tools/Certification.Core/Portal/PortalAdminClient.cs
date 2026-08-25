using System.Net.Http.Json;
using System.Text.Json;

namespace Biason.AutomationAgent.Certification.Core.Portal;

/// <summary>
/// Minimal admin-facing Portal client used by the C# side of the harness:
/// obtaining a fresh Agent registration token before starting Agent.Service
/// (docs/certification-harness.md item 20), and polling Fleet's
/// GET /agents/{id} to confirm real registration/online/heartbeat state
/// (item 63). Automation/version/package/runtime provisioning is handled by
/// the Python backend/tools/certification CLI instead of being duplicated
/// here — see Program.cs's `prepare` command.
/// </summary>
public sealed class PortalAdminClient
{
    private readonly HttpClient _http;
    private string? _bearerToken;

    public PortalAdminClient(HttpClient http)
    {
        _http = http;
    }

    public async Task LoginAsync(string email, string password, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(BuildUri("auth/login"), new { email, password }, ct);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: ct);
        _bearerToken = payload.GetProperty("access_token").GetString();
    }

    private void ApplyAuth(HttpRequestMessage request)
    {
        if (_bearerToken is not null)
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", _bearerToken);
    }

    /// <summary>
    /// Creates a fresh, short-lived registration token. This is the value
    /// injected into the certification Agent's environment as
    /// AUTOMATION_AGENT_Portal__RegistrationToken — never written to a
    /// checked-in file (docs/certification-harness.md items 20-21).
    /// </summary>
    public async Task<string> CreateRegistrationTokenAsync(int expiresInSeconds, CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, BuildUri("agents/registration-tokens"))
        {
            Content = JsonContent.Create(new { expires_in_seconds = expiresInSeconds })
        };
        ApplyAuth(request);
        var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: ct);
        return payload.GetProperty("registration_token").GetString()
            ?? throw new InvalidOperationException("Portal returned an empty registration_token.");
    }

    public async Task<JsonElement?> FindAgentByNameAsync(string displayName, CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, BuildUri("agents"));
        ApplyAuth(request);
        var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        var agents = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: ct);

        foreach (var agent in agents.EnumerateArray())
        {
            if (agent.TryGetProperty("name", out var name) &&
                string.Equals(name.GetString(), displayName, StringComparison.Ordinal))
            {
                return agent;
            }
        }
        return null;
    }

    public async Task<JsonElement> GetAgentAsync(string agentId, CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, BuildUri($"agents/{agentId}"));
        ApplyAuth(request);
        var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: ct);
    }

    public async Task DisableAgentAsync(string agentId, string reason, CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, BuildUri($"agents/{agentId}/disable"))
        {
            Content = JsonContent.Create(new { reason })
        };
        ApplyAuth(request);
        var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
    }

    private Uri BuildUri(string relativePath)
    {
        if (_http.BaseAddress is null)
            return new Uri(relativePath, UriKind.Relative);

        var baseAddress = new Uri(_http.BaseAddress.ToString().TrimEnd('/') + "/");
        return new Uri(baseAddress, relativePath.TrimStart('/'));
    }
}
