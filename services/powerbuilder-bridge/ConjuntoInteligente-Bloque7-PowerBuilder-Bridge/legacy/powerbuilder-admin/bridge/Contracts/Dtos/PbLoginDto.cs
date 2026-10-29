using System.Text.Json.Serialization;

namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;

public sealed class PbLoginRequest
{
    [JsonPropertyName("email")]
    public string Email { get; init; } = "";

    [JsonPropertyName("password")]
    public string Password { get; init; } = "";

    [JsonPropertyName("tenant_id")]
    public string TenantId { get; init; } = "";
}

public sealed class PbLoginResponse
{
    [JsonPropertyName("access_token")]
    public string AccessToken { get; init; } = "";

    [JsonPropertyName("token_type")]
    public string TokenType { get; init; } = "bearer";
}

public sealed record CoreLoginResponse(
    [property: JsonPropertyName("access_token")] string AccessToken,
    [property: JsonPropertyName("token_type")] string TokenType);
