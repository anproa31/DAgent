"""Tool definition and result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass(frozen=True)
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


ToolHandler = Callable[..., Awaitable["ToolResult"]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, ToolParameter]
    handler: ToolHandler

    def parameter_schema(self) -> Dict[str, Any]:
        props: Dict[str, Any] = {}
        required: List[str] = []
        for param in self.parameters.values():
            props[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                props[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)
        return {"type": "object", "properties": props, "required": required}


@dataclass
class ToolResult:
    success: bool
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_observation_artifacts(self) -> Dict[str, Any]:
        artifacts = dict(self.data)
        artifacts["chunks"] = self.chunks
        return artifacts
