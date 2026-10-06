"""The tool list the agent's prompt shows, written compactly from the tool registry.

`tool_registry.tool_reference` prints each tool's full JSON schema, which repeats the filter's
schema in four tools (about 6,000 characters, paid at every step). This writes one signature
line per tool from the same argument models, and the filter once, so the prompt still cannot
drift from what the API accepts.
"""

from __future__ import annotations

from typing import Any

from plantgraph.qa.plant_api.model import ItemFilter
from plantgraph.qa.plant_api.tool_registry import TOOLS


def compact_tool_reference() -> str:
    """The filter's fields, then `name(arguments): description` for every tool."""
    filter_fields = _signature(ItemFilter.model_json_schema())
    lines = [
        f"ItemFilter (an object; every field optional, all set fields must match): {filter_fields}"
    ]
    for spec in TOOLS.values():
        lines.append(
            f"{spec.name}({_signature(spec.args_model.model_json_schema())}): {spec.description}"
        )
    return "\n".join(lines)


def _signature(schema: dict[str, Any]) -> str:
    """`name: type` per argument; an optional one is `name?: type`, with a simple default shown."""
    required = set(schema.get("required", []))
    parts = []
    for name, prop in schema["properties"].items():
        optional = "" if name in required else "?"
        default = _simple_default(prop)
        parts.append(f"{name}{optional}: {_type_of(prop)}{default}")
    return ", ".join(parts)


def _type_of(prop: dict[str, Any]) -> str:
    if "$ref" in prop:
        return str(prop["$ref"]).rsplit("/", 1)[-1]
    if "enum" in prop:
        return "|".join(str(value) for value in prop["enum"])
    if "anyOf" in prop:  # `X | None`: the optional marker already says "may be left out"
        non_null = [option for option in prop["anyOf"] if option.get("type") != "null"]
        return _type_of(non_null[0])
    return str(prop["type"])


def _simple_default(prop: dict[str, Any]) -> str:
    default = prop.get("default")
    if default is None or isinstance(default, dict):
        return ""
    return f" = {str(default).lower() if isinstance(default, bool) else default}"
