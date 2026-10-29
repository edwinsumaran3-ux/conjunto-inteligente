using System.Text.Json.Serialization;
using System.Text.Json;

namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;

[JsonConverter(typeof(PbOptionalJsonConverterFactory))]
public sealed class PbOptional<T>(T? value)
{
    public T? Value { get; } = value;
}

public sealed class PbOptionalJsonConverterFactory : JsonConverterFactory
{
    public override bool CanConvert(Type typeToConvert) =>
        typeToConvert.IsGenericType
        && typeToConvert.GetGenericTypeDefinition() == typeof(PbOptional<>);

    public override JsonConverter CreateConverter(Type typeToConvert, JsonSerializerOptions options)
    {
        var valueType = typeToConvert.GetGenericArguments()[0];
        var converterType = typeof(PbOptionalJsonConverter<>).MakeGenericType(valueType);
        return (JsonConverter)Activator.CreateInstance(converterType, nonPublic: true)!;
    }

    private sealed class PbOptionalJsonConverter<TValue> : JsonConverter<PbOptional<TValue>>
    {
        public override bool HandleNull => true;

        public override PbOptional<TValue> Read(
            ref Utf8JsonReader reader,
            Type typeToConvert,
            JsonSerializerOptions options)
        {
            var value = reader.TokenType == JsonTokenType.Null
                ? default
                : JsonSerializer.Deserialize<TValue>(ref reader, options);
            return new PbOptional<TValue>(value);
        }

        public override void Write(
            Utf8JsonWriter writer,
            PbOptional<TValue> value,
            JsonSerializerOptions options) =>
            JsonSerializer.Serialize(writer, value.Value, options);
    }
}

public sealed class PbOrderCreateRequest
{
    [JsonPropertyName("title")] public string Title { get; init; } = "";
    [JsonPropertyName("description")] public string Description { get; init; } = "";
    [JsonPropertyName("category")] public string Category { get; init; } = "";
    [JsonPropertyName("severity")] public string Severity { get; init; } = "medium";
    [JsonPropertyName("property_id")] public Guid? PropertyId { get; init; }
    [JsonPropertyName("unit_id")] public Guid? UnitId { get; init; }
    [JsonPropertyName("asset_node_id")] public Guid? AssetNodeId { get; init; }
    [JsonPropertyName("resident_id")] public Guid? ResidentId { get; init; }
    [JsonPropertyName("vendor_id")] public Guid? VendorId { get; init; }
    [JsonPropertyName("cost_cop")] public decimal? CostCop { get; init; }
    [JsonPropertyName("sla_due_at")] public DateTimeOffset? SlaDueAt { get; init; }
}

public sealed class PbOrderUpdateRequest
{
    [JsonPropertyName("description")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public PbOptional<string?>? Description { get; init; }
    [JsonPropertyName("vendor_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public PbOptional<Guid?>? VendorId { get; init; }
    [JsonPropertyName("cost_cop")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public PbOptional<decimal?>? CostCop { get; init; }
    [JsonPropertyName("sla_due_at")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public PbOptional<DateTimeOffset?>? SlaDueAt { get; init; }
    [JsonPropertyName("expected_version")] public int ExpectedVersion { get; init; }
}

public sealed class PbApprovalRequest
{
    [JsonPropertyName("note")] public string? Note { get; init; }
    [JsonPropertyName("expected_version")] public int ExpectedVersion { get; init; }
}

public sealed class PbOrderStatusRequest
{
    [JsonPropertyName("status")] public string Status { get; init; } = "";
    [JsonPropertyName("note")] public string? Note { get; init; }
    [JsonPropertyName("expected_version")] public int ExpectedVersion { get; init; }
}

public sealed class PbResidentCreateRequest
{
    [JsonPropertyName("user_id")] public Guid UserId { get; init; }
    [JsonPropertyName("full_name")] public string FullName { get; init; } = "";
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("unit_ids")] public IReadOnlyList<Guid> UnitIds { get; init; } = [];
    [JsonPropertyName("primary_unit_id")] public Guid PrimaryUnitId { get; init; }
}

public sealed class PbResidentUpdateRequest
{
    [JsonPropertyName("full_name")] public string FullName { get; init; } = "";
    [JsonPropertyName("phone")] public string? Phone { get; init; }
    [JsonPropertyName("active")] public bool Active { get; init; }
    [JsonPropertyName("unit_ids")] public IReadOnlyList<Guid> UnitIds { get; init; } = [];
    [JsonPropertyName("primary_unit_id")] public Guid PrimaryUnitId { get; init; }
}

public sealed class PbVendorRequest
{
    [JsonPropertyName("name")] public string Name { get; init; } = "";
    [JsonPropertyName("nit")] public string Nit { get; init; } = "";
    [JsonPropertyName("categories")] public IReadOnlyList<string> Categories { get; init; } = [];
    [JsonPropertyName("status")] public string Status { get; init; } = "active";
    [JsonPropertyName("documents_valid_until")] public DateOnly? DocumentsValidUntil { get; init; }
    [JsonPropertyName("rating")] public decimal? Rating { get; init; }
}

public sealed record CoreMaintenanceMutation(
    [property: JsonPropertyName("id")] string? Id,
    [property: JsonPropertyName("status")] string? Status,
    [property: JsonPropertyName("version")] int? Version);
