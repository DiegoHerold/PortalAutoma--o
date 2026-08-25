using System.Net;
using System.Text.Json;
using Biason.AutomationAgent.Certification.Core.Portal;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

public class PortalAdminClientTests
{
    [Fact]
    public async Task LoginAndFindAgent_PreserveApiPrefixFromBaseAddress()
    {
        var observedPaths = new List<string>();
        using var http = new HttpClient(new StubHandler(request =>
        {
            observedPaths.Add(request.RequestUri?.AbsolutePath ?? "");
            if (request.RequestUri?.AbsolutePath.EndsWith("/auth/login", StringComparison.Ordinal) == true)
            {
                return Json(new { access_token = "tok_test" });
            }

            request.Headers.Authorization?.Scheme.Should().Be("Bearer");
            request.Headers.Authorization?.Parameter.Should().Be("tok_test");
            return Json(new[]
            {
                new
                {
                    id = "agt_cert",
                    name = "certification-agent-01",
                    connectivity_status = "online",
                    health_status = "healthy",
                    last_seen_at = DateTimeOffset.UtcNow.ToString("O")
                }
            });
        }))
        {
            BaseAddress = new Uri("http://portal.local/api/v1")
        };
        var client = new PortalAdminClient(http);

        await client.LoginAsync("admin@portal.local", "admin123");
        var agent = await client.FindAgentByNameAsync("certification-agent-01");

        observedPaths.Should().Equal("/api/v1/auth/login", "/api/v1/agents");
        agent.Should().NotBeNull();
        agent!.Value.GetProperty("id").GetString().Should().Be("agt_cert");
    }

    private static HttpResponseMessage Json<T>(T value) =>
        new(HttpStatusCode.OK)
        {
            Content = new StringContent(JsonSerializer.Serialize(value))
        };

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(respond(request));
    }
}
