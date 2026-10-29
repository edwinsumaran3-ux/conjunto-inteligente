using System.Net;
using System.Net.Http.Headers;
using Microsoft.AspNetCore.Http;

namespace ConjuntoInteligente.CoreApi;

public sealed class CoreApiProxy
{
    private static readonly HashSet<string> ForwardedRequestHeaders = new(StringComparer.OrdinalIgnoreCase)
    {
        "Accept",
        "Accept-Language",
        "Access-Control-Request-Headers",
        "Access-Control-Request-Method",
        "Authorization",
        "If-Range",
        "Idempotency-Key",
        "If-Match",
        "If-Modified-Since",
        "If-None-Match",
        "If-Unmodified-Since",
        "Origin",
        "Range",
        "User-Agent",
        "X-Correlation-ID",
        "X-Idempotency-Key",
        "X-Request-ID"
    };

    private static readonly HashSet<string> HopByHopHeaders = new(StringComparer.OrdinalIgnoreCase)
    {
        "Connection",
        "Keep-Alive",
        "Proxy-Authenticate",
        "Proxy-Authorization",
        "TE",
        "Trailer",
        "Transfer-Encoding",
        "Upgrade"
    };

    private static readonly HashSet<string> ForwardedContentHeaders = new(StringComparer.OrdinalIgnoreCase)
    {
        "Content-Disposition",
        "Content-Encoding",
        "Content-Language",
        "Content-Location",
        "Content-MD5",
        "Content-Range",
        "Content-Type",
        "Expires",
        "Last-Modified"
    };

    private readonly HttpClient _httpClient;
    private readonly CoreApiOptions _options;
    private readonly ILogger<CoreApiProxy> _logger;

    public CoreApiProxy(
        HttpClient httpClient,
        CoreApiOptions options,
        ILogger<CoreApiProxy> logger)
    {
        _httpClient = httpClient;
        _options = options;
        _logger = logger;
    }

    public async Task ForwardAsync(HttpContext context)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(context.RequestAborted);
        timeout.CancelAfter(_options.RequestTimeout);

        using var outgoing = CreateRequest(context.Request);
        try
        {
            using var incoming = await _httpClient.SendAsync(
                outgoing,
                HttpCompletionOption.ResponseHeadersRead,
                timeout.Token);

            context.Response.StatusCode = (int)incoming.StatusCode;
            CopyResponseHeaders(incoming, context.Response);
            context.Response.Headers.CacheControl = "no-store";
            context.Response.Headers.Pragma = "no-cache";

            if (incoming.Content is not null && context.Request.Method != HttpMethods.Head)
            {
                await incoming.Content.CopyToAsync(context.Response.Body, timeout.Token);
            }
        }
        catch (OperationCanceledException) when (!context.RequestAborted.IsCancellationRequested)
        {
            _logger.LogWarning("Timeout al reenviar {Method} {Path} al ERP API.",
                context.Request.Method, context.Request.Path);
            await WriteGatewayErrorAsync(context, StatusCodes.Status504GatewayTimeout,
                "core_api_timeout", "La API ERP excedió el tiempo de respuesta.");
        }
        catch (HttpRequestException exception)
        {
            _logger.LogWarning(exception, "No se pudo reenviar {Method} {Path} al ERP API.",
                context.Request.Method, context.Request.Path);
            await WriteGatewayErrorAsync(context, StatusCodes.Status502BadGateway,
                "core_api_unavailable", "La API ERP no está disponible.");
        }
    }

    public async Task<bool> IsCoreReadyAsync(CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_options.ReadinessTimeout);

        try
        {
            using var response = await _httpClient.GetAsync(
                new Uri(_options.BaseUri, "readyz"),
                HttpCompletionOption.ResponseHeadersRead,
                timeout.Token);
            if (response.IsSuccessStatusCode)
            {
                return true;
            }

            _logger.LogWarning("ERP API readiness devolvió HTTP {StatusCode}.",
                (int)response.StatusCode);
            return false;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            _logger.LogWarning("Timeout consultando readiness de ERP API.");
            return false;
        }
        catch (HttpRequestException exception)
        {
            _logger.LogWarning(exception, "No se pudo consultar readiness de ERP API.");
            return false;
        }
    }

    private HttpRequestMessage CreateRequest(HttpRequest request)
    {
        var pathAndQuery = request.Path.ToUriComponent() + request.QueryString.ToUriComponent();
        var target = new Uri(_options.BaseUri, pathAndQuery);
        var outgoing = new HttpRequestMessage(new HttpMethod(request.Method), target)
        {
            Version = HttpVersion.Version11,
            VersionPolicy = HttpVersionPolicy.RequestVersionOrLower
        };

        foreach (var headerName in ForwardedRequestHeaders)
        {
            if (request.Headers.TryGetValue(headerName, out var values))
            {
                outgoing.Headers.TryAddWithoutValidation(headerName, values.ToArray());
            }
        }

        if (HasRequestContent(request))
        {
            var content = new StreamContent(request.Body);
            foreach (var headerName in ForwardedContentHeaders)
            {
                if (request.Headers.TryGetValue(headerName, out var values))
                {
                    content.Headers.TryAddWithoutValidation(headerName, values.ToArray());
                }
            }

            outgoing.Content = content;
        }

        return outgoing;
    }

    private static bool HasRequestContent(HttpRequest request) =>
        request.ContentLength is not null
        || request.Headers.ContainsKey("Transfer-Encoding")
        || request.Headers.ContainsKey("Content-Type")
        || HttpMethods.IsPost(request.Method)
        || HttpMethods.IsPut(request.Method)
        || HttpMethods.IsPatch(request.Method)
        || HttpMethods.IsDelete(request.Method);

    private static void CopyResponseHeaders(HttpResponseMessage incoming, HttpResponse outgoing)
    {
        var hopByHop = new HashSet<string>(HopByHopHeaders, StringComparer.OrdinalIgnoreCase);
        AddConnectionTokens(incoming.Headers, hopByHop);
        AddConnectionTokens(incoming.Content?.Headers, hopByHop);

        CopyHeaders(incoming.Headers, outgoing.Headers, hopByHop);
        if (incoming.Content is not null)
        {
            CopyHeaders(incoming.Content.Headers, outgoing.Headers, hopByHop);
        }
    }

    private static void AddConnectionTokens(HttpHeaders? headers, ISet<string> excluded)
    {
        if (headers is null || !headers.TryGetValues("Connection", out var values))
        {
            return;
        }

        foreach (var token in values.SelectMany(value => value.Split(',')))
        {
            var name = token.Trim();
            if (name.Length > 0)
            {
                excluded.Add(name);
            }
        }
    }

    private static void CopyHeaders(
        HttpHeaders source,
        IHeaderDictionary destination,
        ISet<string> excluded)
    {
        foreach (var header in source)
        {
            if (!excluded.Contains(header.Key))
            {
                destination[header.Key] = header.Value.ToArray();
            }
        }
    }

    private static async Task WriteGatewayErrorAsync(
        HttpContext context,
        int statusCode,
        string code,
        string message)
    {
        if (context.Response.HasStarted)
        {
            return;
        }

        context.Response.Clear();
        context.Response.StatusCode = statusCode;
        context.Response.ContentType = "application/problem+json";
        await context.Response.WriteAsJsonAsync(
            new { status = statusCode, code, message, traceId = context.TraceIdentifier },
            cancellationToken: context.RequestAborted);
    }
}
