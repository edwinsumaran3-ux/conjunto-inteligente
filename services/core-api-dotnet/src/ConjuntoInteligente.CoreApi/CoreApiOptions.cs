namespace ConjuntoInteligente.CoreApi;

public sealed record CoreApiOptions(
    Uri BaseUri,
    TimeSpan RequestTimeout,
    TimeSpan ReadinessTimeout)
{
    public static CoreApiOptions FromConfiguration(IConfiguration configuration)
    {
        var section = configuration.GetSection("CoreApi");
        var rawBaseUrl = section["BaseUrl"];
        if (!Uri.TryCreate(rawBaseUrl, UriKind.Absolute, out var baseUri)
            || (baseUri.Scheme != Uri.UriSchemeHttp && baseUri.Scheme != Uri.UriSchemeHttps)
            || !string.IsNullOrEmpty(baseUri.UserInfo)
            || baseUri.AbsolutePath != "/"
            || !string.IsNullOrEmpty(baseUri.Query)
            || !string.IsNullOrEmpty(baseUri.Fragment))
        {
            throw new InvalidOperationException(
                "CoreApi:BaseUrl debe ser un origen HTTP(S) absoluto, sin credenciales ni ruta.");
        }

        var requestTimeout = ReadPositiveSeconds(section, "RequestTimeoutSeconds", 120);
        var readinessTimeout = ReadPositiveSeconds(section, "ReadinessTimeoutSeconds", 3);
        return new CoreApiOptions(
            new Uri(baseUri.GetLeftPart(UriPartial.Authority) + "/", UriKind.Absolute),
            TimeSpan.FromSeconds(requestTimeout),
            TimeSpan.FromSeconds(readinessTimeout));
    }

    private static int ReadPositiveSeconds(IConfigurationSection section, string key, int fallback)
    {
        var rawValue = section[key];
        if (rawValue is null)
        {
            return fallback;
        }

        if (!int.TryParse(rawValue, out var value) || value <= 0)
        {
            throw new InvalidOperationException($"CoreApi:{key} debe ser un entero positivo.");
        }

        return value;
    }
}
