namespace ConjuntoInteligente.PbBridge.Contracts;
public static class PbErrorCodes
{
    public const string Ok="OK"; public const string Unauthorized="PB_AUTH_REQUIRED"; public const string Forbidden="PB_FORBIDDEN";
    public const string NotFound="PB_NOT_FOUND"; public const string ValidationError="PB_VALIDATION"; public const string CoreUnavailable="PB_CORE_UNAVAILABLE";
    public const string CoreTimeout="PB_CORE_TIMEOUT"; public const string CoreError="PB_CORE_ERROR"; public const string InternalError="PB_INTERNAL"; public const string RateLimited="PB_RATE_LIMITED";
}
