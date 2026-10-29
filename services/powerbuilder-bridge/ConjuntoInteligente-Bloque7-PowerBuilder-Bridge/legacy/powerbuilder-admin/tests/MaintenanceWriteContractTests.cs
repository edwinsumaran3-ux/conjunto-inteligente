using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using ConjuntoInteligente.PbBridge.Contracts.Dtos;
using FluentAssertions;
using WireMock.RequestBuilders;
using WireMock.ResponseBuilders;

namespace ConjuntoInteligente.PbBridge.Tests;

public sealed class MaintenanceWriteContractTests(PbBridgeFactory factory)
    : IClassFixture<PbBridgeFactory>
{
    private const string DevToken = "dev-token-not-for-production-0000";
    private const string UserJwt = "user-jwt";

    [Fact]
    public async Task Order_create_forwards_user_jwt_to_erp()
    {
        factory.CoreMock.Reset();
        factory.CoreMock
            .Given(Request.Create()
                .WithPath("/api/v1/maintenance/orders")
                .UsingPost()
                .WithHeader("Authorization", "Bearer user-jwt"))
            .RespondWith(Response.Create()
                .WithStatusCode(201)
                .WithHeader("Content-Type", "application/json")
                .WithBodyAsJson(new
                {
                    id = "e194d92c-6e9a-45b4-b97f-639d3cb5eb10",
                    code = "MT-00000001",
                    status = "pending_approval"
                }));

        using var client = CreateAuthenticatedClient();
        var response = await client.PostAsJsonAsync(
            "/pb/v1/orders",
            new PbOrderCreateRequest
            {
                Title = "Luz en parqueadero",
                Category = "iluminacion"
            });

        response.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    [Fact]
    public async Task Order_approval_and_status_transition_forward_to_erp()
    {
        const string orderId = "e194d92c-6e9a-45b4-b97f-639d3cb5eb10";
        factory.CoreMock.Reset();
        factory.CoreMock
            .Given(Request.Create()
                .WithPath($"/api/v1/maintenance/orders/{orderId}/approve")
                .UsingPost()
                .WithHeader("Authorization", "Bearer user-jwt"))
            .RespondWith(Response.Create()
                .WithStatusCode(200)
                .WithHeader("Content-Type", "application/json")
                .WithBodyAsJson(new { id = orderId, status = "scheduled", version = 2 }));
        factory.CoreMock
            .Given(Request.Create()
                .WithPath($"/api/v1/maintenance/orders/{orderId}/status")
                .UsingPatch()
                .WithHeader("Authorization", "Bearer user-jwt"))
            .RespondWith(Response.Create()
                .WithStatusCode(200)
                .WithHeader("Content-Type", "application/json")
                .WithBodyAsJson(new { id = orderId, status = "in_progress", version = 3 }));

        using var client = CreateAuthenticatedClient();
        var approval = await client.PostAsJsonAsync(
            $"/pb/v1/orders/{orderId}/approve",
            new PbApprovalRequest { ExpectedVersion = 1 });
        var transition = await client.PatchAsJsonAsync(
            $"/pb/v1/orders/{orderId}/status",
            new PbOrderStatusRequest
            {
                Status = "in_progress",
                ExpectedVersion = 2
            });

        approval.StatusCode.Should().Be(HttpStatusCode.OK);
        transition.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public void Order_patch_preserves_omitted_and_explicit_null_values()
    {
        var json = JsonSerializer.Serialize(
            new PbOrderUpdateRequest
            {
                Description = new PbOptional<string?>("updated"),
                VendorId = new PbOptional<Guid?>((Guid?)null),
                ExpectedVersion = 4
            },
            new JsonSerializerOptions(JsonSerializerDefaults.Web));
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        root.GetProperty("description").GetString().Should().Be("updated");
        root.GetProperty("vendor_id").ValueKind.Should().Be(JsonValueKind.Null);
        root.TryGetProperty("cost_cop", out _).Should().BeFalse();
        root.GetProperty("expected_version").GetInt32().Should().Be(4);
    }

    [Fact]
    public async Task Resident_and_vendor_writes_use_the_maintenance_contract()
    {
        const string residentId = "cb9930ed-9f4f-4bbb-8e74-ae28e650b2ab";
        const string vendorId = "62af9cf9-0353-4176-9bd5-f35f796cb64a";
        factory.CoreMock.Reset();
        factory.CoreMock
            .Given(Request.Create()
                .WithPath("/api/v1/maintenance/residents")
                .UsingPost()
                .WithHeader("Authorization", "Bearer user-jwt"))
            .RespondWith(Response.Create()
                .WithStatusCode(201)
                .WithHeader("Content-Type", "application/json")
                .WithBodyAsJson(new { id = residentId, status = "created" }));
        factory.CoreMock
            .Given(Request.Create()
                .WithPath($"/api/v1/maintenance/vendors/{vendorId}")
                .UsingPut()
                .WithHeader("Authorization", "Bearer user-jwt"))
            .RespondWith(Response.Create()
                .WithStatusCode(200)
                .WithHeader("Content-Type", "application/json")
                .WithBodyAsJson(new { id = vendorId, status = "updated" }));

        using var client = CreateAuthenticatedClient();
        var resident = await client.PostAsJsonAsync(
            "/pb/v1/residents",
            new PbResidentCreateRequest
            {
                UserId = Guid.Parse("df3ae22e-9f12-4e51-8420-a9ea4211ae05"),
                FullName = "Residente de prueba",
                UnitIds = [Guid.Parse("304c3cc3-1884-4db4-b288-edaa5a69c611")],
                PrimaryUnitId = Guid.Parse("304c3cc3-1884-4db4-b288-edaa5a69c611")
            });
        var vendor = await client.PutAsJsonAsync(
            $"/pb/v1/vendors/{vendorId}",
            new PbVendorRequest
            {
                Name = "Proveedor de prueba",
                Nit = "900123456",
                Categories = ["iluminacion"]
            });

        resident.StatusCode.Should().Be(HttpStatusCode.Created);
        vendor.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    private HttpClient CreateAuthenticatedClient()
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Add("X-PB-Service-Token", DevToken);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", UserJwt);
        return client;
    }
}
