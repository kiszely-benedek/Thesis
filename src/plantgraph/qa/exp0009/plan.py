"""Which plants EXP-0009 builds: their ids, seeds, sizes and tagging (design §19.1, §19.2).

`prereg/plan.json` is written once, by the draw, before the pre-registration. Every shell script
and every Python step asks this module for a plant instead of keeping its own table.

Two words for a reader outside process engineering. A **sheet** is one drawing page; a plant of
"100 sheets" is one drawn on about 100 pages. A **document** is a group of sheets drawn by one
engineering team; a team may leave the tags off its manual valves (`document_untagged`).

Each plant has two corpus ids. The **A id** (`H100g22p1`) names the corpus the frozen system V2T-A2
reads; the **B id** (`H100g22p1B`) names the same plant for the revised system V2T-B.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.ingest.headline_v22 import HeadlinePresetV22

B_SUFFIX = "B"
PLANTS_PER_SCALE = 5
SCALES = (100, 1000)
GENERATION = HeadlinePresetV22().generation  # "g22"

Scale = Literal[100, 1000]


class Role(str, Enum):
    """What a plant is for."""

    DEV = "dev"  # D100g22: B is tuned on it
    PROBE = "probe"  # D1000g22: composition bands and rules only, never questioned
    VALIDATION = "validation"
    SEALED = "sealed"


def plant_id(role: Role, scale: int, index: int | None = None) -> str:
    """The A id of a plant: `D100g22`, `D1000g22`, `VAL100g22`, `H100g22p3`.

    The id names the nominal scale (100 or 1,000), never the drawn target: a plant whose target
    is 97 sheets is still `H100g22p3`.

    Raises:
        ValueError: the scale is not 100 or 1,000, or `index` does not fit the role.
    """
    if scale not in SCALES:
        raise ValueError(f"expected a nominal scale in {SCALES}, found {scale}")
    if role is Role.SEALED:
        if index is None or not 1 <= index <= PLANTS_PER_SCALE:
            raise ValueError(f"expected a sealed plant number 1-{PLANTS_PER_SCALE}, found {index}")
        return f"H{scale}{GENERATION}p{index}"
    if index is not None:
        raise ValueError(f"expected no plant number for role {role.value}, found {index}")
    prefix = {Role.DEV: "D", Role.PROBE: "D", Role.VALIDATION: "VAL"}[role]
    return f"{prefix}{scale}{GENERATION}"


def b_id_of(a_id: str) -> str:
    """The B corpus id of a plant."""
    return a_id + B_SUFFIX


def a_id_of(b_id: str) -> str:
    """The A corpus id of a B id.

    Raises:
        ValueError: the id does not end in `B`.
    """
    if not b_id.endswith(B_SUFFIX):
        raise ValueError(f"expected a B corpus id (ending in {B_SUFFIX!r}), found {b_id!r}")
    return b_id.removesuffix(B_SUFFIX)


class PlantSpec22(BaseModel):
    """One plant to build, as the draw fixed it."""

    model_config = ConfigDict(frozen=True)

    plant_id: str
    role: Role
    scale: Scale
    seed: int
    #: the sheet count the size search aimed for (drawn inside the scale's band)
    target_sheets: int
    n_units: int = Field(ge=1)
    #: the sheet total the size search predicted; the build must reproduce it exactly (G0k)
    predicted_sheets: int
    #: one flag per document, True = that document's manual valves print no tag
    document_untagged: tuple[bool, ...]

    @property
    def b_id(self) -> str:
        """The B corpus id of this plant."""
        return b_id_of(self.plant_id)

    @property
    def n_documents(self) -> int:
        """How many documents the plant has."""
        return len(self.document_untagged)

    def generator_config(self) -> GeneratorConfigV22:
        """The v2.2 config of this plant, its documents' tagging fixed by `document_untagged`."""
        config = HeadlinePresetV22().generator_config(self.n_units, self.seed)
        knobs = config.handbook.model_copy(update={"document_untagged": self.document_untagged})
        return config.model_copy(update={"handbook": knobs})


class Exp0009Plan(BaseModel):
    """`plan.json`: every plant of EXP-0009 P1, and the facts the draw also fixed."""

    model_config = ConfigDict(frozen=True)

    draw_seed: int
    #: sha256 of `position_prior.json`, the text prior fitted on the dev seeds (design §19.2 step 6)
    prior_sha256: str
    #: form ("tag" or "descriptor") -> its majority position code, as fitted
    majority_code: dict[str, str]
    plants: tuple[PlantSpec22, ...]

    def of_role(self, role: Role, scale: int | None = None) -> list[PlantSpec22]:
        """The plants of a role (one scale only, if given), in plan order."""
        return [p for p in self.plants if p.role is role and scale in (None, p.scale)]

    def plant(self, a_id: str) -> PlantSpec22:
        """The plant with this A id.

        Raises:
            ValueError: no such plant in the plan.
        """
        for spec in self.plants:
            if spec.plant_id == a_id:
                return spec
        raise ValueError(f"expected one of {[p.plant_id for p in self.plants]}, found {a_id!r}")

    def sealed_ids(self) -> list[str]:
        """The sealed A ids: the 100-sheet plants first, then the 1,000-sheet ones."""
        return [p.plant_id for p in self.of_role(Role.SEALED)]
