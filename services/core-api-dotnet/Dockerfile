FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY src/ConjuntoInteligente.CoreApi/ConjuntoInteligente.CoreApi.csproj src/ConjuntoInteligente.CoreApi/
RUN dotnet restore src/ConjuntoInteligente.CoreApi/ConjuntoInteligente.CoreApi.csproj
COPY src/ src/
RUN dotnet publish src/ConjuntoInteligente.CoreApi/ConjuntoInteligente.CoreApi.csproj \
    --configuration Release --no-restore --output /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
USER app
ENTRYPOINT ["dotnet", "ConjuntoInteligente.CoreApi.dll"]
