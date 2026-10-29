using System.Security.Cryptography; using System.Text; using ConjuntoInteligente.PbBridge.Contracts;
namespace ConjuntoInteligente.PbBridge.Middleware;
public sealed class PbServiceTokenMiddleware
{
 public const string HeaderName="X-PB-Service-Token"; private readonly RequestDelegate _next; private readonly byte[] _expected; private readonly ILogger<PbServiceTokenMiddleware> _log;
 public PbServiceTokenMiddleware(RequestDelegate next,IConfiguration config,ILogger<PbServiceTokenMiddleware> log){_next=next;_log=log;var token=config["PB:ServiceToken"]??"";if(string.IsNullOrWhiteSpace(token)||token.Length<16)throw new InvalidOperationException("PB:ServiceToken debe estar configurado con al menos 16 caracteres.");_expected=Encoding.UTF8.GetBytes(token);}
 public async Task Invoke(HttpContext ctx){if(ctx.Request.Path.StartsWithSegments("/health")||ctx.Request.Path.StartsWithSegments("/ready")){await _next(ctx);return;}var provided=ctx.Request.Headers[HeaderName].ToString();if(string.IsNullOrEmpty(provided)){await WriteUnauthorized(ctx,"Token de servicio ausente.");return;}var providedBytes=Encoding.UTF8.GetBytes(provided);if(providedBytes.Length!=_expected.Length||!CryptographicOperations.FixedTimeEquals(providedBytes,_expected)){_log.LogWarning("Token PB inválido desde {IP}",ctx.Connection.RemoteIpAddress);await WriteUnauthorized(ctx,"Token de servicio inválido.");return;}await _next(ctx);}
 private static async Task WriteUnauthorized(HttpContext ctx,string msg){ctx.Response.StatusCode=StatusCodes.Status401Unauthorized;ctx.Response.ContentType="application/json";await ctx.Response.WriteAsJsonAsync(PbResponse<object>.Failure(PbErrorCodes.Unauthorized,msg));}
}
