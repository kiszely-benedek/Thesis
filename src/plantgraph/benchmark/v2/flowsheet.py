"""The flowsheet grammar: which process units a plant has, and how their ports are wired.

A **flowsheet** is the plant's process flow: which unit operations come in which order. Real plants
are not random graphs, so the grammar lets randomness choose only *among meaningful options*
(design generator-v2-realism.md 8): it never picks two arbitrary nodes to connect.

```
Plant        := Train+            a train's product farm is the next train's feed farm
Train        := FeedFarm Conditioning{0..2} Core Separation{1..3} ProductFarm
FeedFarm     := U4                (the first train only)
Conditioning := U5 | U7 | U8
Core         := U3 [U2 on its gas outlet] | U6
Separation   := U1 | U6
ProductFarm  := U4
```

`U1`..`U8` are the process patterns (`patterns/`). Only the patterns that exist take part: a slot
draws among the available ones, so the grammar stays valid while patterns are added. U10 (a crude
desalter) has no entry on purpose: it is not generated. A slot that is empty (no available pattern)
is skipped when optional and an error when required.

Randomness and determinism (design 8.2): the master stream `random.Random(f"{seed}:flowsheet")`
draws the unit sequence train by train, so the first *n* units of a larger plant are the *n*-unit
plant. A unit's internals use their own stream and are built in `planner.py`.

Wiring (`wire`): a unit's first in-port takes the latest open out-port of the same phase
(a gas out-port never feeds a liquid in-port). A product farm also takes the liquid streams its own
train left open (a column's distillate and side draw), through extra receipt lines (v2.1; v2
left them as open stubs). Out-ports nobody takes stay open: an open stub.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.v2.config import FlowsheetKnobs
from plantgraph.benchmark.v2.patterns.ports import (
    PatternInstance,
    Phase,
    Port,
    PortDirection,
    PortKind,
    with_in_port_source,
    with_out_port_destination,
)
from plantgraph.benchmark.v2.streams import master_rng

_FARM = "U4"
_COMPOSITE_SEPARATOR = "+"  # a weight key `U3+U2` is two units drawn together
_REACTOR, _RECYCLE_COMPRESSOR = "U3", "U2"


class Slot(str, Enum):
    """The place of a unit in a train."""

    FEED_FARM = "feed_farm"
    CONDITIONING = "conditioning"
    CORE = "core"
    SEPARATION = "separation"
    PRODUCT_FARM = "product_farm"


#: the drawing title each slot gives its unit (`FIL Feed conditioning`)
SLOT_TITLES: dict[Slot, str] = {
    Slot.FEED_FARM: "Feed tank farm",
    Slot.CONDITIONING: "Feed conditioning",
    Slot.CORE: "Core",
    Slot.SEPARATION: "Separation",
    Slot.PRODUCT_FARM: "Product tank farm",
}


class UnitSlot(BaseModel):
    """One process unit of the plant: its number, its train, its place and its pattern."""

    model_config = ConfigDict(frozen=True)

    unit_no: int = Field(ge=1)
    train_no: int = Field(ge=1)
    slot: Slot
    pattern_id: str  # `U6`


def draw_flowsheet(
    seed: int, n_units: int, knobs: FlowsheetKnobs, available: frozenset[str]
) -> tuple[UnitSlot, ...]:
    """The first `n_units` units of the plant, train after train; the last train may be cut short.

    Raises:
        ValueError: the farm pattern, or every pattern of a required slot, is not available.
    """
    if _FARM not in available:
        raise ValueError(
            f"the grammar needs the tank farm {_FARM!r}; available: {sorted(available)}"
        )
    rng = master_rng(seed)
    units: list[tuple[int, Slot, str]] = []
    train_no = 0
    while len(units) < n_units:
        train_no += 1
        units += [
            (train_no, slot, pid) for slot, pid in _draw_train(rng, knobs, available, train_no)
        ]
    return tuple(
        UnitSlot(unit_no=number, train_no=train, slot=slot, pattern_id=pid)
        for number, (train, slot, pid) in enumerate(units[:n_units], start=1)
    )


def _draw_train(
    rng: random.Random, knobs: FlowsheetKnobs, available: frozenset[str], train_no: int
) -> list[tuple[Slot, str]]:
    """The slots of one train in flow order; the feed farm only for the first train."""
    conditioning = _slot_weights(knobs.conditioning_weights, available)
    core = _slot_weights(knobs.core_weights, available)
    separation = _slot_weights(knobs.separation_weights, available)
    train: list[tuple[Slot, str]] = [(Slot.FEED_FARM, _FARM)] if train_no == 1 else []
    count = _draw(rng, knobs.conditioning_count_weights) if conditioning else 0
    train += [(Slot.CONDITIONING, _draw(rng, conditioning)) for _ in range(count)]
    train += _composite_units(Slot.CORE, _draw(rng, _required(core, "core")))
    for _ in range(_draw(rng, knobs.separation_count_weights)):
        train.append((Slot.SEPARATION, _draw(rng, _required(separation, "separation"))))
    train.append((Slot.PRODUCT_FARM, _FARM))
    return train


def _slot_weights(weights: Mapping[str, float], available: frozenset[str]) -> dict[str, float]:
    """The weights of the options whose patterns all exist (`U3+U2` needs both)."""
    return {
        key: weight
        for key, weight in sorted(weights.items())
        if set(key.split(_COMPOSITE_SEPARATOR)) <= available
    }


def _required(weights: dict[str, float], slot_name: str) -> dict[str, float]:
    if not weights:
        raise ValueError(f"no available pattern can fill the required {slot_name} slot")
    return weights


def _composite_units(slot: Slot, key: str) -> list[tuple[Slot, str]]:
    return [(slot, pattern_id) for pattern_id in key.split(_COMPOSITE_SEPARATOR)]


def _draw[K: (int, str)](rng: random.Random, weights: Mapping[K, float]) -> K:
    """One key of `weights`, chosen in proportion to its weight (keys sorted: deterministic)."""
    keys = sorted(weights)
    return rng.choices(keys, weights=[weights[key] for key in keys])[0]


# ---- wiring --------------------------------------------------------------------------------------


class OpenOut(BaseModel):
    """An out-port that no later unit has taken (yet)."""

    model_config = ConfigDict(frozen=True)

    unit_no: int
    port: Port
    train_no: int = 1  # the train of the unit that owns the port


def wire(
    instance: PatternInstance,
    unit_no: int,
    open_outs: tuple[OpenOut, ...],
    train_no: int = 1,
) -> tuple[PatternInstance, tuple[OpenOut, ...]]:
    """Feed the instance's in-ports from open out-ports of the same phase.

    The first in-port takes the latest open out-port, whatever its train. Every further in-port
    that `collects` (a tank farm's extra receipt lines) takes the latest one left by a unit of the
    same train: that is where a column's distillate and side draw end (v2.1). Returns the instance
    with the joins made and the open out-ports afterwards: the taken ones are gone, this unit's
    own out-ports are added. With nothing to take (the first unit of the plant) an in-port stays
    open: the plant's feed enters there.
    """
    in_ports = [port for port in instance.ports if port.direction is PortDirection.IN]
    if not in_ports:
        raise ValueError(f"{instance.pattern} has no in-port; its ports are {instance.port_names}")
    taken: list[OpenOut] = []
    for position, in_port in enumerate(in_ports):
        if position > 0 and not in_port.collects:
            continue
        pool = [out for out in open_outs if out not in taken]
        source = _latest_to_take(pool, in_port, None if position == 0 else train_no)
        if source is not None:
            instance = with_in_port_source(instance, in_port.name, source.port.node_id)
            taken.append(source)
    remaining = tuple(out for out in open_outs if out not in taken)
    own = tuple(
        OpenOut(unit_no=unit_no, port=port, train_no=train_no)
        for port in instance.ports
        if port.direction is PortDirection.OUT
    )
    return instance, remaining + own


def closes_recycle_loop(slot: UnitSlot, previous: UnitSlot | None) -> bool:
    """True for the compressor half of a `U3+U2` core: it sits right behind its reactor."""
    return (
        slot.pattern_id == _RECYCLE_COMPRESSOR
        and previous is not None
        and previous.pattern_id == _REACTOR
        and previous.train_no == slot.train_no
    )


def close_recycle_loop(
    reactor: PatternInstance,
    compressor: PatternInstance,
    compressor_unit_no: int,
    open_outs: tuple[OpenOut, ...],
) -> tuple[PatternInstance, tuple[OpenOut, ...]]:
    """Return the compressor's gas to the reactor's `recycle_gas` in-port (v2.2, handbook on).

    The compressor's `compressed` line ends at the first part of the reactor's `recycle_gas` line,
    and that out-port stops being an open stub. No random draw is made, so no stream shifts.
    """
    # rule PLT-STREAM-CLOSURE: recycle loop closed per the grammar (Toghraei 2019 p.24; DESIGN)
    # the join is stored on the compressor's line: it is the later unit, and a backend may only
    # name parts that were written before (the reactor's line cannot name a part of the compressor)
    compressed = compressor.port("compressed")
    closed = with_out_port_destination(
        compressor, compressed.name, reactor.port("recycle_gas").node_id
    )
    still_open = tuple(
        out
        for out in open_outs
        if not (out.unit_no == compressor_unit_no and out.port.name == compressed.name)
    )
    return closed, still_open


def waiting_streams(open_outs: tuple[OpenOut, ...], train_no: int) -> int:
    """How many liquid process streams of train `train_no` no unit has taken yet."""
    return sum(
        1
        for out in open_outs
        if out.train_no == train_no
        and out.port.phase is Phase.LIQUID
        and out.port.kind is PortKind.PROCESS
    )


def _latest_to_take(pool: list[OpenOut], in_port: Port, train_no: int | None) -> OpenOut | None:
    """The most recently opened out-port with the in-port's phase (of `train_no`, if given)."""
    # rule PLT-PHASE: a port only takes a stream of its own phase (DESIGN S12)
    matching = [
        out for out in pool if out.port.phase is in_port.phase and train_no in (None, out.train_no)
    ]
    return matching[-1] if matching else None
