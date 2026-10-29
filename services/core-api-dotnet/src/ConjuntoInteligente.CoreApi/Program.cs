using ConjuntoInteligente.CoreApi;

var builder = WebApplication.CreateBuilder(args);
var coreOptions = CoreApiOptions.FromConfiguration(builder.Configuration);

builder.Services.AddSingleton(coreOptions);
builder.Services.AddHttpClient<CoreApiProxy>(client =>
{
    client.Timeout = Timeout.InfiniteTimeSpan;
});

var app = builder.Build();

app.MapGet("/healthz", () => Results.Ok(new { status = "ok", service = "core-api-dotnet" }));
app.MapGet("/readyz", async (CoreApiProxy proxy, HttpContext context) =>
{
    var ready = await proxy.IsCoreReadyAsync(context.RequestAborted);
    return ready
        ? Results.Ok(new { status = "ready", dependency = "erp-api" })
        : Results.Json(
            new { status = "not_ready", dependency = "erp-api" },
            statusCode: StatusCodes.Status503ServiceUnavailable);
});

var proxyMethods = new[] { "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS" };
app.MapMethods("/api/v1/{**path}", proxyMethods,
    (HttpContext context, CoreApiProxy proxy) => proxy.ForwardAsync(context));
app.MapMethods("/openapi.json", ["GET", "HEAD"],
    (HttpContext context, CoreApiProxy proxy) => proxy.ForwardAsync(context));
app.MapMethods("/docs", ["GET", "HEAD"],
    (HttpContext context, CoreApiProxy proxy) => proxy.ForwardAsync(context));
app.MapMethods("/docs/{**path}", ["GET", "HEAD"],
    (HttpContext context, CoreApiProxy proxy) => proxy.ForwardAsync(context));
app.MapMethods("/redoc", ["GET", "HEAD"],
    (HttpContext context, CoreApiProxy proxy) => proxy.ForwardAsync(context));

app.Run();

public partial class Program;
