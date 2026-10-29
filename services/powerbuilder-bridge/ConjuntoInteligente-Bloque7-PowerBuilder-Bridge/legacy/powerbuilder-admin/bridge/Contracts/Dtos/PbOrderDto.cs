using System.Text.Json.Serialization;
namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;
public sealed class PbOrderDto
{
 [JsonPropertyName("id")] public string Id{get;init;}=""; [JsonPropertyName("codigo")] public string Codigo{get;init;}=""; [JsonPropertyName("titulo")] public string Titulo{get;init;}="";
 [JsonPropertyName("categoria")] public string Categoria{get;init;}=""; [JsonPropertyName("severidad")] public string Severidad{get;init;}=""; [JsonPropertyName("estado")] public string Estado{get;init;}="";
 [JsonPropertyName("area")] public string Area{get;init;}=""; [JsonPropertyName("zona")] public string Zona{get;init;}=""; [JsonPropertyName("activoId")] public string? ActivoId{get;init;}
 [JsonPropertyName("reporto")] public string Reporto{get;init;}=""; [JsonPropertyName("proveedor")] public string? Proveedor{get;init;} [JsonPropertyName("costoCop")] public decimal? CostoCop{get;init;}
 [JsonPropertyName("propertyId")] public string? PropertyId{get;init;} [JsonPropertyName("unitId")] public string? UnitId{get;init;}
 [JsonPropertyName("residentId")] public string? ResidentId{get;init;} [JsonPropertyName("vendorId")] public string? VendorId{get;init;}
 [JsonPropertyName("creadaEn")] public string CreadaEn{get;init;}=""; [JsonPropertyName("actualizadaEn")] public string ActualizadaEn{get;init;}=""; [JsonPropertyName("slaVenceEn")] public string? SlaVenceEn{get;init;}
 [JsonPropertyName("descripcion")] public string Descripcion{get;init;}="";
}
public sealed class PbOrderListRequest
{
 [JsonPropertyName("estado")] public string? Estado{get;init;} [JsonPropertyName("categoria")] public string? Categoria{get;init;} [JsonPropertyName("busqueda")] public string? Busqueda{get;init;}
 [JsonPropertyName("desde")] public string? Desde{get;init;} [JsonPropertyName("hasta")] public string? Hasta{get;init;} [JsonPropertyName("pagina")] public int Pagina{get;init;}=1; [JsonPropertyName("porPagina")] public int PorPagina{get;init;}=50;
}
public sealed class PbOrderListResponse
{
 [JsonPropertyName("items")] public IReadOnlyList<PbOrderDto> Items{get;init;}=[]; [JsonPropertyName("total")] public int Total{get;init;}
 [JsonPropertyName("pagina")] public int Pagina{get;init;} [JsonPropertyName("porPagina")] public int PorPagina{get;init;}
}
