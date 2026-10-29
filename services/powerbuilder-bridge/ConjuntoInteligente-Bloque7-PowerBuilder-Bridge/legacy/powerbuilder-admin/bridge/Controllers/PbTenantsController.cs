using ConjuntoInteligente.PbBridge.Contracts; using ConjuntoInteligente.PbBridge.Contracts.Dtos; using ConjuntoInteligente.PbBridge.Services; using Microsoft.AspNetCore.Mvc;
namespace ConjuntoInteligente.PbBridge.Controllers;
[Route("pb/v1/tenants")] public sealed class PbTenantsController:PbBaseController{private readonly ICoreClient _core;private readonly IPbMapper _mapper;public PbTenantsController(ICoreClient core,IPbMapper mapper){_core=core;_mapper=mapper;}
 [HttpGet("current")] public async Task<IActionResult> GetCurrent(CancellationToken ct){var t=await _core.GetAsync<CoreTenant>("api/v1/tenants/current",ct);if(t is null)return PbFail(PbErrorCodes.NotFound,"Tenant no encontrado.",404);return PbOk(_mapper.ToPb(t));}
 [HttpGet] public async Task<IActionResult> List(CancellationToken ct){var t=await _core.GetAsync<CoreTenant>("api/v1/tenants/current",ct);return t is null?PbOk(Array.Empty<PbTenantDto>()):PbOk(new[]{_mapper.ToPb(t)});}}
