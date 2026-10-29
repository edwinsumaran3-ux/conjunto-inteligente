namespace ConjuntoInteligente.PbBridge.Services;
public sealed class CoreClientOptions
{
    public string BaseUrl { get; set; } = "http://localhost:5000";
    public int TimeoutSeconds { get; set; } = 10;
    public int RetryCount { get; set; } = 2;
}
