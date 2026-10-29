namespace ConjuntoInteligente.PbBridge.Services;
public interface ICoreClient
{
    Task<T?> GetAsync<T>(string path, CancellationToken ct) where T : class;
    Task<T?> PostAsync<T>(string path, object body, CancellationToken ct) where T : class;
    Task<T?> PutAsync<T>(string path, object body, CancellationToken ct) where T : class;
    Task<T?> PatchAsync<T>(string path, object body, CancellationToken ct) where T : class;
}
