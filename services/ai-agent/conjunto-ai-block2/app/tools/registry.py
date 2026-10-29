from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

ToolCallable = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    function: ToolCallable


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, function: ToolCallable) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = ToolDefinition(name, description, function)

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    async def execute(self, name: str, **kwargs: Any) -> Any:
        return await self.get(name).function(**kwargs)
