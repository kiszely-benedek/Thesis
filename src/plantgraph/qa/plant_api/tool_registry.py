"""The six primitives as named tools with argument schemas (design §3.3, §5.1).

An agent names a tool and passes a JSON object; `call_tool` checks the object
against the tool's Pydantic argument model and runs it. The same models
generate the tool reference the agent's prompt shows, so the prompt cannot
drift from what the API accepts.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from plantgraph.qa.plant_api.model import (
    Direction,
    GroupBy,
    ItemFilter,
    PlantApiError,
    RelationGroup,
)
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import DEFAULT_MAX_ITEMS, PlantResult


class _Args(BaseModel):
    """Base of every argument model: an unknown key is an error, not ignored."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class FindArgs(_Args):
    """Arguments of `find`."""

    where: ItemFilter = ItemFilter()
    limit: int = DEFAULT_MAX_ITEMS


class NeighboursArgs(_Args):
    """Arguments of `neighbours`."""

    of: str
    direction: Direction
    relations: RelationGroup
    where: ItemFilter | None = None


class TraverseArgs(_Args):
    """Arguments of `traverse`."""

    start: str
    direction: Direction
    relations: RelationGroup
    stop_at: ItemFilter | None = None
    walk_only: ItemFilter | None = None
    max_hops: int | None = None


class PathArgs(_Args):
    """Arguments of `path`."""

    source: str
    target: str
    relations: RelationGroup = "flow"
    directed: bool = True


class FilterArgs(_Args):
    """Arguments of `filter`."""

    items: str
    where: ItemFilter


class AggregateArgs(_Args):
    """Arguments of `aggregate`."""

    items: str
    group_by: GroupBy


@dataclass(frozen=True)
class ToolSpec:
    """One tool: its name, a one-line description, its argument model and how to run it."""

    name: str
    description: str
    args_model: type[BaseModel]
    run: Callable[[PlantApi, Any], PlantResult]


def _find(api: PlantApi, args: FindArgs) -> PlantResult:
    return api.find(args.where, args.limit)


def _neighbours(api: PlantApi, args: NeighboursArgs) -> PlantResult:
    return api.neighbours(args.of, args.direction, args.relations, args.where)


def _traverse(api: PlantApi, args: TraverseArgs) -> PlantResult:
    return api.traverse(
        args.start, args.direction, args.relations, args.stop_at, args.walk_only, args.max_hops
    )


def _path(api: PlantApi, args: PathArgs) -> PlantResult:
    return api.path(args.source, args.target, args.relations, args.directed)


def _filter(api: PlantApi, args: FilterArgs) -> PlantResult:
    return api.filter(args.items, args.where)


def _aggregate(api: PlantApi, args: AggregateArgs) -> PlantResult:
    return api.aggregate(args.items, args.group_by)


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "find", "Items matching a filter, sorted by tag, with the total count.", FindArgs, _find
        ),
        ToolSpec(
            "neighbours",
            "Items one hop from a tag or handle, with the edges used.",
            NeighboursArgs,
            _neighbours,
        ),
        ToolSpec(
            "traverse",
            "Everything reachable from a tag or handle; stop_at ends a branch after "
            "including the stop item, walk_only never enters other items.",
            TraverseArgs,
            _traverse,
        ),
        ToolSpec(
            "path",
            "Shortest path between two tags or handles, with the sheets it crosses.",
            PathArgs,
            _path,
        ),
        ToolSpec("filter", "The items of a handle that match a filter.", FilterArgs, _filter),
        ToolSpec(
            "aggregate",
            "Count a handle's items per node_class, unit or sheet.",
            AggregateArgs,
            _aggregate,
        ),
    )
}


def call_tool(api: PlantApi, name: str, arguments: Mapping[str, Any]) -> PlantResult:
    """Validate `arguments` against the named tool and run it.

    Raises:
        PlantApiError: unknown tool, invalid arguments, or the call itself failed.
    """
    spec = TOOLS.get(name)
    if spec is None:
        raise PlantApiError(f"expected one of the tools {sorted(TOOLS)}, found {name!r}")
    try:
        args = spec.args_model.model_validate(dict(arguments))
    except ValidationError as error:
        raise PlantApiError(f"invalid arguments for {name}: {_summarize(error)}") from error
    return spec.run(api, args)


def _summarize(error: ValidationError) -> str:
    """`field: message` per problem, on one line."""
    problems = (f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
    return "; ".join(problems)


def tool_reference() -> str:
    """The prompt text listing every tool, its description and its argument JSON schema."""
    blocks = []
    for spec in TOOLS.values():
        schema = json.dumps(spec.args_model.model_json_schema(), separators=(",", ":"))
        blocks.append(f"{spec.name}: {spec.description}\n  arguments: {schema}")
    return "\n".join(blocks)
