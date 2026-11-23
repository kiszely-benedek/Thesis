"""Documents: the run of trains that one contractor's drawing set covers (v2.2, design 5, 18.2).

A **document** is one company's set of drawings, about 100 sheets. Every real multi-sheet set we
hold keeps one convention on all its sheets, so v2.2 draws the company conventions once per
document, not once per train: whether manual valves print a tag, how spares are numbered, the
letter of an on-off valve, and whether a pressure-control station has a bypass.

A document is the plant **area** of `network_models.area_of_train` (design 17.14 N2.3), so one knob,
`HandbookKnobs.trains_per_area`, says how many trains a document holds. Its draws come from streams
named by the document alone (`streams.handbook_document_rng`); the v2.1 per-train draws are still
taken by the planner and their values are ignored, so no v2.1 draw moves.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.network_models import area_of_train, first_train_of_area
from plantgraph.benchmark.v2.plan_models import TrainRecord
from plantgraph.benchmark.v2.streams import handbook_document_rng
from plantgraph.benchmark.v2.v21_pins import (
    V21_ON_OFF_LETTER_WEIGHTS,
    V21_ON_OFF_LETTERS,
    V21_SPARE_NAMING_WEIGHTS,
    V21_SPARE_NAMINGS,
)
from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming, TrainConventions


class DocumentRecord(BaseModel):
    """One document and the four conventions it keeps on every sheet (gold, never in the graph)."""

    model_config = ConfigDict(frozen=True)

    document_no: int = Field(ge=1)
    first_train: int = Field(ge=1)
    last_train: int = Field(ge=1)
    conventions: TrainConventions  # the on-off valve letter and the spare naming
    #: manual and check valves print no tag (Toghraei p.113); automatic valves, safety devices
    #: and instruments always do
    manual_valves_untagged: bool
    #: pressure-control stations are drawn without a bypass (Toghraei p.122)
    pv_without_bypass: bool


def document_of_train(train_no: int, trains_per_document: int) -> int:
    """The document (from 1) of a train: the area of the train, a function of the train alone."""
    return area_of_train(train_no, trains_per_document)


def draw_documents(config: GeneratorConfigV22, n_trains: int) -> tuple[DocumentRecord, ...]:
    """The documents of a plant of `n_trains` trains, each drawn from its own streams."""
    per_document = config.handbook.trains_per_document
    n_documents = document_of_train(n_trains, per_document)
    overrides = _checked_overrides(config, n_documents)
    return tuple(
        _draw_document(config, number, n_trains, overrides) for number in range(1, n_documents + 1)
    )


def _checked_overrides(config: GeneratorConfigV22, n_documents: int) -> tuple[bool, ...] | None:
    flags = config.handbook.document_untagged
    if flags is not None and len(flags) < n_documents:
        raise ValueError(
            f"expected handbook.document_untagged to give one flag per document "
            f"({n_documents} documents), found {len(flags)}"
        )
    return flags


def _draw_document(
    config: GeneratorConfigV22, number: int, n_trains: int, overrides: tuple[bool, ...] | None
) -> DocumentRecord:
    knobs = config.handbook
    seed = config.seed
    first = first_train_of_area(number, knobs.trains_per_document)
    # the coin is flipped even when the allocation is fixed, so a stratified plant and a drawn
    # one read the same streams
    untagged = handbook_document_rng(seed, number, "untagged_manual_valves").random()
    letter = handbook_document_rng(seed, number, "on_off_letter")
    naming = handbook_document_rng(seed, number, "spare_naming")
    pv_coin = handbook_document_rng(seed, number, "pv_no_bypass").random()
    return DocumentRecord(
        document_no=number,
        first_train=first,
        last_train=min(first + knobs.trains_per_document - 1, n_trains),
        conventions=TrainConventions(
            on_off_letter=OnOffLetter(
                letter.choices(V21_ON_OFF_LETTERS, weights=V21_ON_OFF_LETTER_WEIGHTS)[0]
            ),
            spare_naming=SpareNaming(
                naming.choices(V21_SPARE_NAMINGS, weights=V21_SPARE_NAMING_WEIGHTS)[0]
            ),
        ),
        manual_valves_untagged=(
            overrides[number - 1]
            if overrides is not None
            else untagged < knobs.p_untagged_manual_document
        ),
        pv_without_bypass=pv_coin < knobs.p_pv_no_bypass_document,
    )


def trains_with_document_conventions(
    trains: tuple[TrainRecord, ...], documents: tuple[DocumentRecord, ...], per_document: int
) -> tuple[TrainRecord, ...]:
    """The trains with their own v2.1 draws replaced by their document's conventions."""
    return tuple(
        train.model_copy(
            update={
                "conventions": documents[
                    document_of_train(train.train_no, per_document) - 1
                ].conventions
            }
        )
        for train in trains
    )
