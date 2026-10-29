using System.Text.Json.Serialization;

namespace ConjuntoInteligente.PbBridge.Services;
using ConjuntoInteligente.PbBridge.Contracts.Dtos;
public interface IPbMapper{PbOrderDto ToPb(CoreOrder source); IReadOnlyList<PbOrderDto> ToPb(IEnumerable<CoreOrder> source); PbResidentDto ToPb(CoreResident source); PbVendorDto ToPb(CoreVendor source); PbTenantDto ToPb(CoreTenant source);}
public sealed record CoreOrder(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("category")] string Category,
    [property: JsonPropertyName("severity")] string Severity,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("area_name")] string AreaName,
    [property: JsonPropertyName("zone_name")] string ZoneName,
    [property: JsonPropertyName("asset_node_id")] string? AssetId,
    [property: JsonPropertyName("reporter_kind")] string ReporterKind,
    [property: JsonPropertyName("reporter_name")] string ReporterName,
    [property: JsonPropertyName("vendor_name")] string? VendorName,
    [property: JsonPropertyName("cost_cop")] decimal? CostCop,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt,
    [property: JsonPropertyName("updated_at")] DateTimeOffset UpdatedAt,
    [property: JsonPropertyName("sla_due_at")] DateTimeOffset? SlaDueAt,
    [property: JsonPropertyName("description")] string Description,
    [property: JsonPropertyName("property_id")] string? PropertyId = null,
    [property: JsonPropertyName("unit_id")] string? UnitId = null,
    [property: JsonPropertyName("resident_id")] string? ResidentId = null,
    [property: JsonPropertyName("vendor_id")] string? VendorId = null);
public sealed record CoreResident(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("property_name")] string? PropertyName,
    [property: JsonPropertyName("unit_code")] string? UnitCode,
    [property: JsonPropertyName("unit_name")] string? UnitName,
    [property: JsonPropertyName("full_name")] string FullName,
    [property: JsonPropertyName("email")] string Email,
    [property: JsonPropertyName("phone")] string? Phone,
    [property: JsonPropertyName("active")] bool Active,
    [property: JsonPropertyName("balance_cop")] decimal? BalanceCop,
    [property: JsonPropertyName("unit_ids")] IReadOnlyList<Guid>? UnitIds = null);
public sealed record CoreVendor(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("nit")] string Nit,
    [property: JsonPropertyName("categories")] IReadOnlyList<string> Categories,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("documents_current")] bool DocsValid,
    [property: JsonPropertyName("rating")] decimal? Rating);
public sealed record CoreTenant(
    [property: JsonPropertyName("id")] Guid Id,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("is_active")] bool Active,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt);
