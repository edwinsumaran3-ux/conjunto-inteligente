using ConjuntoInteligente.PbBridge.Contracts;
using ConjuntoInteligente.PbBridge.Contracts.Dtos;
using ConjuntoInteligente.PbBridge.Services;
using Microsoft.AspNetCore.Mvc;

namespace ConjuntoInteligente.PbBridge.Controllers;

[Route("pb/v1/auth")]
public sealed class PbAuthController(ICoreClient core) : PbBaseController
{
    [HttpPost("login")]
    public async Task<IActionResult> Login(
        [FromBody] PbLoginRequest request,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Email)
            || string.IsNullOrWhiteSpace(request.Password)
            || !Guid.TryParse(request.TenantId, out _))
        {
            return PbFail(
                PbErrorCodes.ValidationError,
                "email, contraseña y tenant_id válido son obligatorios.");
        }

        var token = await core.PostAsync<CoreLoginResponse>(
            "api/v1/auth/login",
            request,
            cancellationToken);
        if (token is null || string.IsNullOrWhiteSpace(token.AccessToken))
        {
            return PbFail(PbErrorCodes.CoreError, "El core no devolvió un token de acceso.", 502);
        }

        return PbOk(new PbLoginResponse
        {
            AccessToken = token.AccessToken,
            TokenType = token.TokenType
        });
    }
}
