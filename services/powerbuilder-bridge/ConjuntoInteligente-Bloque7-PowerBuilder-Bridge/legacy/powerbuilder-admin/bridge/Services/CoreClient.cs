using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Options;

namespace ConjuntoInteligente.PbBridge.Services;

public sealed class CoreClient : ICoreClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly HttpClient _http;
    private readonly IHttpContextAccessor _contextAccessor;
    private readonly ILogger<CoreClient> _log;

    public CoreClient(
        HttpClient http,
        IHttpContextAccessor contextAccessor,
        IOptions<CoreClientOptions> options,
        ILogger<CoreClient> log)
    {
        _http = http;
        _contextAccessor = contextAccessor;
        _log = log;
        var baseUrl = options.Value.BaseUrl;
        if (string.IsNullOrWhiteSpace(baseUrl))
        {
            throw new InvalidOperationException("CoreClientOptions.BaseUrl es obligatorio.");
        }

        _http.BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/");
        _http.Timeout = TimeSpan.FromSeconds(options.Value.TimeoutSeconds);
        _http.DefaultRequestHeaders.Accept.ParseAdd("application/json");
    }

    public async Task<T?> GetAsync<T>(string path, CancellationToken ct) where T : class
    {
        using var request = CreateRequest(HttpMethod.Get, path);
        using var response = await _http.SendAsync(request, ct);
        return await HandleAsync<T>(response, path, ct);
    }

    public async Task<T?> PostAsync<T>(string path, object body, CancellationToken ct) where T : class
    {
        return await SendAsync<T>(HttpMethod.Post, path, body, ct);
    }

    public async Task<T?> PutAsync<T>(string path, object body, CancellationToken ct) where T : class
    {
        return await SendAsync<T>(HttpMethod.Put, path, body, ct);
    }

    public async Task<T?> PatchAsync<T>(string path, object body, CancellationToken ct) where T : class
    {
        return await SendAsync<T>(HttpMethod.Patch, path, body, ct);
    }

    private async Task<T?> SendAsync<T>(
        HttpMethod method,
        string path,
        object body,
        CancellationToken ct) where T : class
    {
        using var request = CreateRequest(method, path);
        request.Content = JsonContent.Create(body, options: JsonOptions);
        using var response = await _http.SendAsync(request, ct);
        return await HandleAsync<T>(response, path, ct);
    }

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
    {
        var request = new HttpRequestMessage(method, path);
        var authorization = _contextAccessor.HttpContext?.Request.Headers.Authorization.ToString();
        if (!string.IsNullOrWhiteSpace(authorization)
            && AuthenticationHeaderValue.TryParse(authorization, out var parsed)
            && string.Equals(parsed.Scheme, "Bearer", StringComparison.OrdinalIgnoreCase))
        {
            request.Headers.Authorization = parsed;
        }

        return request;
    }

    private async Task<T?> HandleAsync<T>(
        HttpResponseMessage response,
        string path,
        CancellationToken ct) where T : class
    {
        if (response.StatusCode == HttpStatusCode.NotFound)
        {
            _log.LogInformation("Core 404 en {Path}", path);
            return null;
        }

        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
        {
            throw new CoreUnauthorizedException((int)response.StatusCode);
        }

        if (response.StatusCode == HttpStatusCode.TooManyRequests)
        {
            throw new CoreRateLimitedException();
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(ct);
            _log.LogWarning("Core {Status} en {Path}: {Body}",
                (int)response.StatusCode, path, body);
            throw new CoreHttpException((int)response.StatusCode, body);
        }

        if (response.StatusCode == HttpStatusCode.NoContent
            || response.Content.Headers.ContentLength == 0)
        {
            return null;
        }

        return await response.Content.ReadFromJsonAsync<T>(JsonOptions, ct);
    }
}

public sealed class CoreHttpException(int statusCode, string body)
    : Exception($"Core error HTTP {statusCode}")
{
    public int StatusCode { get; } = statusCode;
    public string Body { get; } = body;
}

public sealed class CoreUnauthorizedException(int statusCode)
    : Exception("Core rechazó la autenticación del usuario.")
{
    public int StatusCode { get; } = statusCode;
}

public sealed class CoreRateLimitedException()
    : Exception("Core aplicó rate limit al bridge.");
