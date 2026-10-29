using System.Text.Json.Serialization;
namespace ConjuntoInteligente.PbBridge.Contracts;
public sealed class PbResponse<T>
{
    [JsonPropertyName("ok")] public bool Ok { get; init; }
    [JsonPropertyName("code")] public string Code { get; init; } = "OK";
    [JsonPropertyName("message")] public string Message { get; init; } = "";
    [JsonPropertyName("data")] public T? Data { get; init; }
    [JsonPropertyName("errors")] public IReadOnlyList<PbError>? Errors { get; init; }
    [JsonPropertyName("traceId")] public string? TraceId { get; init; }
    [JsonPropertyName("ts")] public string Ts { get; init; } = DateTimeOffset.UtcNow.ToString("O");
    public static PbResponse<T> Success(T data, string message = "") => new() { Ok = true, Code = "OK", Message = message, Data = data };
    public static PbResponse<T> Failure(string code, string message, params PbError[] errors) => new() { Ok = false, Code = code, Message = message, Errors = errors.Length == 0 ? null : errors };
}
public sealed record PbError([property: JsonPropertyName("field")] string? Field,[property: JsonPropertyName("message")] string Message);
