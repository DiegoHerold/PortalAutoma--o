namespace Biason.AutomationAgent.Certification.Core.Portal;

public sealed record ProbeResult(bool Healthy, string? Detail);

/// <summary>
/// Real Portal/Gateway health probes (docs/certification-harness.md items
/// 17-19). No fabricated readiness: every result comes from an actual HTTP
/// call to the real endpoints exercised by
/// backend/gateway/agent_gateway/tests/smoke_gateway_flow.py and the
/// Portal's own health routes.
/// </summary>
public sealed class PortalHealth
{
    private readonly HttpClient _http;

    public PortalHealth(HttpClient http)
    {
        _http = http;
    }

    public async Task<ProbeResult> CheckPortalHealthAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync(BuildUri("health"), ct);
            if (!response.IsSuccessStatusCode)
                return new ProbeResult(false, $"HTTP {(int)response.StatusCode}");
            var body = await response.Content.ReadAsStringAsync(ct);
            return new ProbeResult(true, body);
        }
        catch (Exception ex)
        {
            return new ProbeResult(false, ex.Message);
        }
    }

    public async Task<ProbeResult> CheckGatewayHealthAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync(BuildUri("agent-gateway/health"), ct);
            return new ProbeResult(response.IsSuccessStatusCode, $"HTTP {(int)response.StatusCode}");
        }
        catch (Exception ex)
        {
            return new ProbeResult(false, ex.Message);
        }
    }

    public async Task<ProbeResult> CheckGatewayReadinessAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync(BuildUri("agent-gateway/readiness"), ct);
            return new ProbeResult(response.IsSuccessStatusCode, $"HTTP {(int)response.StatusCode}");
        }
        catch (Exception ex)
        {
            return new ProbeResult(false, ex.Message);
        }
    }

    /// <summary>
    /// Polls a probe until it reports healthy or the timeout elapses.
    /// Never loops forever (docs/certification-harness.md item 46).
    /// </summary>
    public static async Task<bool> WaitUntilAsync(
        Func<CancellationToken, Task<ProbeResult>> probe,
        TimeSpan timeout,
        TimeSpan interval,
        CancellationToken ct = default)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(timeout);
        try
        {
            while (!cts.IsCancellationRequested)
            {
                var result = await probe(cts.Token);
                if (result.Healthy)
                    return true;
                await Task.Delay(interval, cts.Token);
            }
        }
        catch (OperationCanceledException)
        {
            // Timed out.
        }
        return false;
    }

    private Uri BuildUri(string relativePath)
    {
        if (_http.BaseAddress is null)
            return new Uri(relativePath, UriKind.Relative);

        var baseAddress = new Uri(_http.BaseAddress.ToString().TrimEnd('/') + "/");
        return new Uri(baseAddress, relativePath.TrimStart('/'));
    }
}
