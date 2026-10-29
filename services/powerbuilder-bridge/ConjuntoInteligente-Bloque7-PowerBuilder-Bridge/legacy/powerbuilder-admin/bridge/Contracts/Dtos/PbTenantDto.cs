using System.Text.Json.Serialization;
namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;
public sealed class PbTenantDto
{
 [JsonPropertyName("id")] public string Id {get;init;}=""; [JsonPropertyName("codigo")] public string? Codigo {get;init;} [JsonPropertyName("nombre")] public string Nombre {get;init;}="";
 [JsonPropertyName("pais")] public string? Pais {get;init;} [JsonPropertyName("zonaHoraria")] public string? ZonaHoraria {get;init;} [JsonPropertyName("moneda")] public string? Moneda {get;init;}
 [JsonPropertyName("activo")] public bool Activo {get;init;} [JsonPropertyName("creadoEn")] public string CreadoEn {get;init;}="";
}
