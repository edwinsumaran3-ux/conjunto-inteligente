from app.integrations.core_client import CoreClient
from app.tools.core_tools import CoreTools
from app.tools.registry import ToolRegistry


def build_tool_registry(client: CoreClient | None = None) -> ToolRegistry:
    core_client = client or CoreClient()
    tools = CoreTools(core_client)
    registry = ToolRegistry()
    registry.register(
        "get_asset_history",
        "Obtains maintenance and operational history for an asset.",
        tools.get_asset_history,
    )
    registry.register(
        "get_area_by_keywords",
        "Searches Core for an operational area matching keywords.",
        tools.search_area,
    )
    return registry
