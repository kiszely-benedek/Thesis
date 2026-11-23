"""The v2.2 generator config: the v2.1 settings plus the handbook-rule knobs (design 9, ADR-0066).

`GeneratorConfigV22` is a subclass of `GeneratorConfigV2`, so the planner, the patterns and every
`isinstance(config, GeneratorConfigV2)` test treat a v2.2 plant as a member of the v2 line; only its
`generator_version` and the extra `handbook` group differ. `GeneratorConfigV2` itself is untouched,
so a v2.1 config's JSON stays byte-identical (pinned in `tests/v2/test_v21_goldens.py`).

Like the v2.1 knobs, every weight here is a **declared** parameter: no handbook gives a rate, so
the values are neutral (even odds) and the field comment names the design table that declares it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from plantgraph.benchmark.v2.config import GeneratorConfigV2, Probability
from plantgraph.benchmark.v2.hidden_state import PumpPowerBand, RefluxClass

FailAction = Literal["FO", "FC", "FL"]  # fail open, fail closed, fail in last position
ExchangerBypass = Literal["tv_alone", "two_control_valves"]
FuelSwitching = Literal["one_valve", "two_in_series"]

#: the service families that join a header on a network sheet (decision D4, recommended set):
#: flare, closed drain, cooling water supply and return, three steam levels' condensate, fuel gas
NETWORK_SERVICES: tuple[str, ...] = ("FL", "CHD", "CWS", "CWR", "LPS", "MPS", "CD", "FG")


def _default_fail_actions() -> dict[str, FailAction]:
    """Design 8: only the min-flow row has a source (Toghraei 2019 p.115); the rest is declared.

    `hx_main_cv` is the exchanger-branch valve of a TOG322 pair; it must differ from `other`, the
    entry of its partner on the bypass, so the two valves move in opposite directions.
    """
    return {
        "min_flow_fv": "FO",
        "anti_surge_fv": "FO",
        "fuel_tv": "FC",
        "fuel_xv": "FC",
        "cooling_water_tv": "FO",
        "steam_tv": "FC",
        "hx_main_cv": "FO",
        "other": "FC",
    }


def _even_weights[K](*keys: K) -> dict[K, float]:
    return {key: 1.0 for key in keys}


def _even_bypass() -> dict[ExchangerBypass, float]:
    return _even_weights("tv_alone", "two_control_valves")


def _even_fuel_switching() -> dict[FuelSwitching, float]:
    return _even_weights("one_valve", "two_in_series")


class HandbookKnobs(BaseModel):
    """The choices a handbook rule leaves open, each with a declared weight (design 5)."""

    #: master switch: False makes every v2.2 behaviour inert, so the plant equals the v2.1 plant
    enabled: bool = True
    #: per document: manual valves are drawn without a tag (Toghraei p.113); 9 of 12 real drawing
    #: sets are untagged (design 18.2)
    p_untagged_manual_document: Probability = 0.75
    #: per document: the plant's stratified allocation, one flag per document in order (True =
    #: manual valves untagged); replaces the draw above, which is still taken (design 5, 18.3)
    document_untagged: tuple[bool, ...] | None = None
    #: per document: pressure-control stations are drawn without a bypass
    p_pv_no_bypass_document: Probability = 0.5
    #: per pump set: nozzle reducers on the pump's suction and discharge; 3 of the 4 real sets
    #: that draw pump trims have them (design 18.2)
    p_pump_reducers: Probability = 0.75
    #: per pump set: the hidden power band, from which the min-flow method follows
    pump_power_weights: dict[PumpPowerBand, float] = Field(
        default_factory=lambda: _even_weights(*PumpPowerBand)
    )
    #: per item: the three variants of battery-limit isolation, numbered as in design 4
    battery_limit_variant_weights: dict[int, float] = Field(
        default_factory=lambda: _even_weights(1, 2, 3)
    )
    #: per item: an exchanger bypass is a temperature valve alone, or two control valves
    exchanger_bypass_weights: dict[ExchangerBypass, float] = Field(default_factory=_even_bypass)
    #: per furnace: one fuel switching valve, or two in series
    fuel_switching_weights: dict[FuelSwitching, float] = Field(default_factory=_even_fuel_switching)
    #: per column: the hidden reflux class, which decides the accumulator split pairing
    reflux_class_weights: dict[RefluxClass, float] = Field(
        default_factory=lambda: _even_weights(*RefluxClass)
    )
    #: service of an actuator -> fail action (declared table, design 8)
    fail_action_table: dict[str, FailAction] = Field(default_factory=_default_fail_actions)
    #: tie-ins one network sheet holds before the header continues on the next (design 7)
    max_tie_ins_per_network_sheet: int = Field(default=16, ge=1)
    network_services: tuple[str, ...] = NETWORK_SERVICES
    #: consecutive trains per area: the run of trains one header serves and one document covers
    #: (design 17.14 N2.1). Fixed by the rule that makes the median area nearest 100 sheets
    trains_per_area: int = Field(default=10, ge=1)

    @property
    def trains_per_document(self) -> int:
        """A document is an area (design 17.14 N2.3): one knob, one meaning."""
        return self.trains_per_area

    @field_validator(
        "pump_power_weights",
        "battery_limit_variant_weights",
        "exchanger_bypass_weights",
        "fuel_switching_weights",
        "reflux_class_weights",
    )
    @classmethod
    def _check_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        non_positive = {str(key): value for key, value in weights.items() if value <= 0}
        if non_positive:
            raise ValueError(f"handbook weights must be strictly positive; got {non_positive}")
        return weights

    @classmethod
    def all_off(cls) -> HandbookKnobs:
        """Every knob at its off position: no v2.2 behaviour, so the plant equals v2.1."""
        return cls(
            enabled=False,
            p_untagged_manual_document=0.0,
            p_pv_no_bypass_document=0.0,
            p_pump_reducers=0.0,
        )


class GeneratorConfigV22(GeneratorConfigV2):
    """Everything the v2.2 generator reads: the v2.1 settings and the `handbook` group."""

    # a deliberate narrowing of the parent's Literal["v2.1"]; the type checker cannot express it
    generator_version: Literal["v2.2"] = "v2.2"  # type: ignore[assignment]
    handbook: HandbookKnobs = Field(default_factory=HandbookKnobs)

    def v21_equivalent(self) -> GeneratorConfigV2:
        """The v2.1 config of the same plant: same settings, version `v2.1`, no handbook group."""
        settings = self.model_dump(exclude={"generator_version", "handbook"})
        return GeneratorConfigV2.model_validate(settings)
