using ConjuntoInteligente.PbBridge.Contracts; using Microsoft.AspNetCore.Mvc;
namespace ConjuntoInteligente.PbBridge.Controllers;
[ApiController] public abstract class PbBaseController:ControllerBase{protected IActionResult PbOk<T>(T data,string message="")=>Ok(PbResponse<T>.Success(data,message));protected IActionResult PbFail(string code,string message,int status=400)=>StatusCode(status,PbResponse<object>.Failure(code,message));}
