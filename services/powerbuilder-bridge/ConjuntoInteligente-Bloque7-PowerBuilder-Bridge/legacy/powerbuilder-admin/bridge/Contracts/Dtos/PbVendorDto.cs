using System.Text.Json.Serialization;
namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;
public sealed class PbVendorDto
{
 [JsonPropertyName("id")] public string Id{get;init;}=""; [JsonPropertyName("nombre")] public string Nombre{get;init;}=""; [JsonPropertyName("nit")] public string Nit{get;init;}="";
 [JsonPropertyName("categorias")] public IReadOnlyList<string> Categorias{get;init;}=[]; [JsonPropertyName("estado")] public string Estado{get;init;}="";
 [JsonPropertyName("documentosVigentes")] public bool DocumentosVigentes{get;init;} [JsonPropertyName("evaluacion")] public decimal? Evaluacion{get;init;}
}
