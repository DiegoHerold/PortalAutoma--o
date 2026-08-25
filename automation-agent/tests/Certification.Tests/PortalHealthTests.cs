using System.Net;
using Biason.AutomationAgent.Certification.Core.Portal;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

public class PortalHealthTests
{
    [Fact]
    public async Task GatewayHealth_PreservesApiPrefixFromBaseAddress()
    {
        string? observedPath = null;
        using var http = new HttpClient(new StubHandler(request =>
        {
            observedPath = request.RequestUri?.AbsolutePath;
            return new HttpResponseMessage(HttpStatusCode.OK);
        }))
        {
            BaseAddress = new Uri("http://portal.local/api/v1")
        };

        await new PortalHealth(http).CheckGatewayHealthAsync();

        observedPath.Should().Be("/api/v1/agent-gateway/health");
    }

    [Fact]
    public async Task PortalHealth_PreservesApiPrefixFromBaseAddress()
    {
        string? observedPath = null;
        using var http = new HttpClient(new StubHandler(request =>
        {
            observedPath = request.RequestUri?.AbsolutePath;
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("""{"status":"ok"}""")
            };
        }))
        {
            BaseAddress = new Uri("http://portal.local/api/v1")
        };

        await new PortalHealth(http).CheckPortalHealthAsync();

        observedPath.Should().Be("/api/v1/health");
    }

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(respond(request));
    }
}
