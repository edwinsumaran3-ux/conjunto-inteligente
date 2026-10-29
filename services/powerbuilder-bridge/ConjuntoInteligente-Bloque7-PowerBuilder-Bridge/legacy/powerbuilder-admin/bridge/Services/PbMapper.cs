namespace ConjuntoInteligente.PbBridge.Services;
using System.Globalization; using ConjuntoInteligente.PbBridge.Contracts.Dtos;
public sealed class PbMapper:IPbMapper
{
 private static string Iso(DateTimeOffset dt)=>dt.UtcDateTime.ToString("O",CultureInfo.InvariantCulture); private static string? IsoOrNull(DateTimeOffset? dt)=>dt is null?null:Iso(dt.Value);
 public PbOrderDto ToPb(CoreOrder s)=>new(){Id=s.Id,Codigo=s.Code,Titulo=s.Title,Categoria=s.Category,Severidad=s.Severity,Estado=s.Status,Area=s.AreaName,Zona=s.ZoneName,ActivoId=s.AssetId,Reporto=$"{s.ReporterName} ({s.ReporterKind})",Proveedor=s.VendorName,CostoCop=s.CostCop,PropertyId=s.PropertyId,UnitId=s.UnitId,ResidentId=s.ResidentId,VendorId=s.VendorId,CreadaEn=Iso(s.CreatedAt),ActualizadaEn=Iso(s.UpdatedAt),SlaVenceEn=IsoOrNull(s.SlaDueAt),Descripcion=s.Description};
 public IReadOnlyList<PbOrderDto> ToPb(IEnumerable<CoreOrder> source)=>source.Select(ToPb).ToArray();
 public PbResidentDto ToPb(CoreResident s)=>new(){Id=s.Id,Torre=s.PropertyName??"",Unidad=s.UnitName??s.UnitCode??"",Nombre=s.FullName,Email=s.Email,Telefono=s.Phone,Activo=s.Active,SaldoCop=s.BalanceCop,UnitIds=s.UnitIds?.Select(id=>id.ToString()).ToArray()??[]};
 public PbVendorDto ToPb(CoreVendor s)=>new(){Id=s.Id,Nombre=s.Name,Nit=s.Nit,Categorias=s.Categories,Estado=s.Status,DocumentosVigentes=s.DocsValid,Evaluacion=s.Rating};
 public PbTenantDto ToPb(CoreTenant s)=>new(){Id=s.Id.ToString(),Nombre=s.Name,Activo=s.Active,CreadoEn=Iso(s.CreatedAt)};
}
