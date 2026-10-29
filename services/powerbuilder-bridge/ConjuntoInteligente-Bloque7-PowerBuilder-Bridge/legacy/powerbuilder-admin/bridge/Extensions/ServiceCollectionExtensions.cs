using ConjuntoInteligente.PbBridge.Services;

namespace ConjuntoInteligente.PbBridge.Extensions;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddPbBridge(this IServiceCollection services, IConfiguration config)
    {
        services.Configure<CoreClientOptions>(config.GetSection("Core"));
        services.AddHttpContextAccessor();
        services.AddMemoryCache();
        services.AddHttpClient<ICoreClient, CoreClient>()
            .AddStandardResilienceHandler(options =>
            {
                options.Retry.MaxRetryAttempts = 2;
                options.Retry.BackoffType = Polly.DelayBackoffType.Exponential;
                options.Retry.UseJitter = true;
                options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(8);
                options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(20);
                options.CircuitBreaker.FailureRatio = 0.5;
                options.CircuitBreaker.MinimumThroughput = 10;
                options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(30);
                options.CircuitBreaker.BreakDuration = TimeSpan.FromSeconds(15);
            });
        services.AddSingleton<IPbMapper, PbMapper>();
        services.AddHealthChecks();
        return services;
    }
}
