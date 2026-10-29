using System.Text.Json.Serialization;
namespace ConjuntoInteligente.PbBridge.Contracts.Dtos;
public sealed class PbResidentDto
{
 [JsonPropertyName("id")] public string Id{get;init;}=""; [JsonPropertyName("torre")] public string Torre{get;init;}=""; [JsonPropertyName("unidad")] public string Unidad{get;init;}="";
 [JsonPropertyName("nombre")] public string Nombre{get;init;}=""; [JsonPropertyName("email")] public string Email{get;init;}=""; [JsonPropertyName("telefono")] public string? Telefono{get;init;}
 [JsonPropertyName("activo")] public bool Activo{get;init;} [JsonPropertyName("saldoCop")] public decimal? SaldoCop{get;init;}
 [JsonPropertyName("unitIds")] public IReadOnlyList<string> UnitIds{get;init;}=[];
}
