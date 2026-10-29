FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ConjuntoInteligente.PbBridge.csproj ./
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app /p:UseAppHost=false
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app .
ENV ASPNETCORE_URLS=http://+:5100
EXPOSE 5100
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost:5100/health >/dev/null || exit 1
ENTRYPOINT ["dotnet","ConjuntoInteligente.PbBridge.dll"]
