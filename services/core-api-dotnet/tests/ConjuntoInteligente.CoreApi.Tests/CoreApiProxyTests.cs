using System.Net;
using System.Text;
using ConjuntoInteligente.CoreApi;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging.Abstractions;

namespace ConjuntoInteligente.CoreApi.Tests;

public sealed class CoreApiProxyTests
{
    [Fact]
    public async Task Forwards_user_identity_and_body_but_not_untrusted_tenant_headers()
    {
        var handler = new StubHandler(async (request, cancellationToken) =>
        {
            Assert.Equal(
                "http://erp.test/api/v1/digital-twin/nodes?limit=2",
                request.RequestUri?.ToString());
            Assert.Equal("Bearer user-jwt", request.Headers.Authorization?.ToString());
            Assert.True(request.Headers.Contains("Idempotency-Key"));
            Assert.False(request.Headers.Contains("X-Tenant-Id"));
            Assert.False(request.Headers.Contains("X-PB-Service-Token"));
            Assert.Equal(
                """{"node_id":"n-1"}""",
                await request.Content!.ReadAsStringAsync(cancellationToken));

            var response = new HttpResponseMessage(HttpStatusCode.Created)
            {
                Content = new StringContent("""{"id":"n-1"}""", Encoding.UTF8, "application/json")
            };
            response.Headers.TryAddWithoutValidation("X-Core-Trace", "trace-123");
            response.Headers.TryAddWithoutValidation("Connection", "X-Hop");
            response.Headers.TryAddWithoutValidation("X-Hop", "must-not-pass");
            return response;
        });
        var proxy = CreateProxy(handler);
        var context = CreateContext(
            HttpMethods.Post,
            "/api/v1/digital-twin/nodes",
            "?limit=2",
            """{"node_id":"n-1"}""");
        context.Request.Headers.Authorization = "Bearer user-jwt";
        context.Request.Headers["Idempotency-Key"] = "request-1";
        context.Request.Headers["X-Tenant-Id"] = "untrusted-tenant";
        context.Request.Headers["X-PB-Service-Token"] = "secret";

        await proxy.ForwardAsync(context);

        Assert.Equal(StatusCodes.Status201Created, context.Response.StatusCode);
        Assert.Equal("trace-123", context.Response.Headers["X-Core-Trace"]);
        Assert.False(context.Response.Headers.ContainsKey("X-Hop"));
        Assert.Equal("no-store", context.Response.Headers.CacheControl);
        Assert.Equal("""{"id":"n-1"}""", await ReadResponseAsync(context));
    }

    [Fact]
    public async Task Returns_502_when_core_api_cannot_be_reached()
    {
        var proxy = CreateProxy(new StubHandler(
            (_, _) => throw new HttpRequestException("connection failed")));
        var context = CreateContext(HttpMethods.Get, "/api/v1/users", "", "");

        await proxy.ForwardAsync(context);

        Assert.Equal(StatusCodes.Status502BadGateway, context.Response.StatusCode);
        Assert.Contains("core_api_unavailable", await ReadResponseAsync(context));
    }

    [Fact]
    public async Task Returns_504_when_core_api_times_out()
    {
        var proxy = CreateProxy(new StubHandler(
            (_, _) => throw new OperationCanceledException("upstream timeout")));
        var context = CreateContext(HttpMethods.Get, "/api/v1/users", "", "");

        await proxy.ForwardAsync(context);

        Assert.Equal(StatusCodes.Status504GatewayTimeout, context.Response.StatusCode);
        Assert.Contains("core_api_timeout", await ReadResponseAsync(context));
    }

    [Fact]
    public async Task Readiness_is_false_when_core_api_is_not_ready()
    {
        var handler = new StubHandler((request, _) =>
        {
            Assert.Equal("http://erp.test/readyz", request.RequestUri?.ToString());
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.ServiceUnavailable));
        });
        var proxy = CreateProxy(handler);

        Assert.False(await proxy.IsCoreReadyAsync(CancellationToken.None));
    }

    private static CoreApiProxy CreateProxy(HttpMessageHandler handler)
    {
        var client = new HttpClient(handler);
        return new CoreApiProxy(
            client,
            new CoreApiOptions(
                new Uri("http://erp.test/"),
                TimeSpan.FromSeconds(10),
                TimeSpan.FromSeconds(1)),
            NullLogger<CoreApiProxy>.Instance);
    }

    private static DefaultHttpContext CreateContext(
        string method,
        string path,
        string query,
        string body)
    {
        var context = new DefaultHttpContext();
        context.Request.Method = method;
        context.Request.Path = path;
        context.Request.QueryString = new QueryString(query);
        var requestBody = Encoding.UTF8.GetBytes(body);
        context.Request.Body = new MemoryStream(requestBody);
        if (requestBody.Length > 0)
        {
            context.Request.ContentLength = requestBody.Length;
            context.Request.ContentType = "application/json";
        }
        context.Response.Body = new MemoryStream();
        return context;
    }

    private static async Task<string> ReadResponseAsync(DefaultHttpContext context)
    {
        context.Response.Body.Position = 0;
        using var reader = new StreamReader(context.Response.Body, Encoding.UTF8);
        return await reader.ReadToEndAsync();
    }

    private sealed class StubHandler(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send)
        : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) =>
            send(request, cancellationToken);
    }
}
