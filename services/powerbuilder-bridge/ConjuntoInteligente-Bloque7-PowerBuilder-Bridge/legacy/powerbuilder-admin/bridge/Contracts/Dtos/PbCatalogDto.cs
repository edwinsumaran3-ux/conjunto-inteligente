using System.Text.Json.Serialization;
namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;
public sealed class PbCatalogDto
{
 [JsonPropertyName("dominio")] public string Dominio{get;init;}=""; [JsonPropertyName("valores")] public IReadOnlyList<PbCatalogItem> Valores{get;init;}=[];
}
public sealed class PbCatalogItem
{
 [JsonPropertyName("clave")] public string Clave{get;init;}=""; [JsonPropertyName("etiqueta")] public string Etiqueta{get;init;}="";
}
