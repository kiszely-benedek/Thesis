"""Rewrite the tags of reference occurrences, so identity resolution has something to resolve.

Terms: a **tag** is the identifier printed next to a piece of equipment on a drawing (`P-1203A`:
a pump, unit 12, sequence 03, installed-spare letter A). When the splitter draws one item on two
sheets, the second drawing is a **reference occurrence** (a short repeat of the home drawing), and
the splitter writes it with the exact tag. Real drawing sets do not: drafters add separators, drop
zero padding, use another class code. This module re-writes reference tags that way.

It is a **post-split transform** (design `exp0004-v2.md` section 3): it never calls the splitter
and draws from its own random stream per reference, so the variant copy has exactly the same
split as the exact-tag corpus. Only the tag text of reference occurrences changes.

Two operator families, so a decider tuned on one can be tested on the other:
- **format** (tuned on): separator, padding, spare-letter and case changes;
- **naming** (held out): another class code (`P`/`PU`, `E`/`HX`, `K`/`C`) or a unit prefix.

Every operator keeps the item's class and the order of its non-zero digits, so a blocking key made
of the two still finds every true pair. That is by construction: it tests the implementation,
not the robustness of a resolver (design section 3.2).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.v2.tags import EQUIPMENT_SEQUENCE_WIDTH, parse_tag
from plantgraph.benchmark.v2.vocabulary import item_kind

Family = Literal["format", "naming"]

#: Class-code synonyms (design 3.2, user-accepted Q7): `P`/`PU` (OPEN100 `RCS-PU-102A` vs
#: `RC-P102A`), `E`/`HX` (OPEN100 `CVCS-HX-111`), `K`/`C` (this repo's v1 compressor prefix).
CLASS_SYNONYMS: dict[str, str] = {"P": "PU", "E": "HX", "K": "C"}


class VariantConfig(BaseModel):
    """What to vary: which operator families, how many references, from which corpus seed."""

    model_config = ConfigDict(frozen=True)

    profile: Literal["exp0004"]
    families: tuple[Family, ...] = ("format", "naming")
    #: probability that one reference gets a variant tag
    rate: float = Field(default=1.0, ge=0.0, le=1.0)
    #: the corpus seed; each reference derives its own random stream from it
    seed: int

    @field_validator("families")
    @classmethod
    def _families_distinct_and_present(cls, families: tuple[Family, ...]) -> tuple[Family, ...]:
        if not families or len(set(families)) != len(families):
            raise ValueError(f"expected one or more distinct families, found {families!r}")
        return families


class VariantDraw(BaseModel):
    """What was done to one reference. Gold side: never shown to a resolver or a model."""

    model_config = ConfigDict(frozen=True)

    reference_key: str  # "sheet:node_id", as in IdentityGroup.references
    family: Family
    operator: str
    original_tag: str
    variant_tag: str


# --- tag parts and operators -------------------------------------------------------------------


class _TagParts(NamedTuple):
    """A v2 equipment tag `CODE-UNITSEQ[SPARE]` split into its fields (all as text)."""

    code: str
    unit: str
    sequence: str  # zero-padded to EQUIPMENT_SEQUENCE_WIDTH digits
    train: str  # the installed-spare letter, or ""

    def join(self, separator: str = "-", spare_separator: str = "") -> str:
        return f"{self.code}{separator}{self.unit}{self.sequence}{spare_separator}{self.train}"


class _Context(NamedTuple):
    """What an operator may look at: the parsed tag, the item's class and a random stream."""

    parts: _TagParts
    node_class: str
    rng: random.Random


#: An operator returns the new tag, or None when it does not apply to this tag.
_OperatorFunction = Callable[[_Context], str | None]


class _Operator(NamedTuple):
    name: str
    family: Family
    apply: _OperatorFunction


def split_equipment_tag(tag: str) -> _TagParts:
    """Split a v2 equipment tag into fields.

    Raises:
        ValueError: if `tag` is not a v2 equipment tag.
    """
    parsed = parse_tag(tag)
    if parsed is None or parsed.kind != "equipment":
        raise ValueError(f"expected a v2 equipment tag such as 'P-1203A', found {tag!r}")
    sequence = f"{parsed.sequence:0{EQUIPMENT_SEQUENCE_WIDTH}d}"
    return _TagParts(parsed.letters, str(parsed.unit), sequence, parsed.train or "")


def class_uses_code(node_class: str, code: str) -> bool:
    """True if tags of `node_class` may be written with `code` (derived from the vocabulary)."""
    try:
        item_kind(node_class, code)
    except ValueError:
        return False
    return True


def _drop_separator(context: _Context) -> str | None:
    return context.parts.join(separator="")


def _swap_separator(context: _Context) -> str | None:
    return context.parts.join(separator=context.rng.choice((" ", ".")))


def _split_number(context: _Context) -> str | None:
    parts = context.parts
    return f"{parts.code}-{parts.unit}-{parts.sequence}{parts.train}"


def _unpad_sequence(context: _Context) -> str | None:
    parts = context.parts
    unpadded = parts.sequence.lstrip("0")
    if unpadded == parts.sequence:  # no leading zero to drop
        return None
    return parts._replace(sequence=unpadded).join()


def _spare_separator(context: _Context) -> str | None:
    if not context.parts.train:
        return None
    return context.parts.join(spare_separator="-")


def _lower_case(context: _Context) -> str | None:
    return context.parts.join().lower()


def _class_synonym(context: _Context) -> str | None:
    synonym = CLASS_SYNONYMS.get(context.parts.code)
    # guard: a synonym equal to a code this class already uses would read as a different role
    if synonym is None or class_uses_code(context.node_class, synonym):
        return None
    return context.parts._replace(code=synonym).join()


def _unit_prefix(context: _Context) -> str | None:
    parts = context.parts
    prefix = context.rng.choice((parts.unit, f"U{parts.unit}"))
    return f"{prefix}-{parts.code}-{parts.sequence}{parts.train}"


#: Fixed order: the operator draw indexes into the applicable ones in this order.
OPERATORS: tuple[_Operator, ...] = (
    _Operator("drop_separator", "format", _drop_separator),
    _Operator("swap_separator", "format", _swap_separator),
    _Operator("split_number", "format", _split_number),
    _Operator("unpad_sequence", "format", _unpad_sequence),
    _Operator("spare_separator", "format", _spare_separator),
    _Operator("case", "format", _lower_case),
    _Operator("class_synonym", "naming", _class_synonym),
    _Operator("unit_prefix", "naming", _unit_prefix),
)


def applicable_operators(
    family: Family, tag: str, node_class: str, rng: random.Random
) -> list[tuple[str, str]]:
    """The (operator name, variant tag) options of `family` for this tag; each changes the tag."""
    context = _Context(split_equipment_tag(tag), node_class, rng)
    options = [(op.name, op.apply(context)) for op in OPERATORS if op.family == family]
    return [(name, variant) for name, variant in options if variant is not None and variant != tag]


# --- the transform -----------------------------------------------------------------------------


def apply_tag_variants(
    sheets: list[SheetGraph], manifest: SplitManifest, config: VariantConfig
) -> tuple[list[SheetGraph], SplitManifest, list[VariantDraw]]:
    """Return copies of `sheets` and `manifest` whose reference tags are re-written.

    Inputs are not modified. Home occurrences and everything but reference tags are unchanged.

    Raises:
        ValueError: if a reference is missing, already varied, or not a v2 equipment tag.
    """
    new_sheets = [
        SheetGraph(sheet.sheet_id, sheet.graph.copy(), list(sheet.connectors)) for sheet in sheets
    ]
    by_id = {sheet.sheet_id: sheet for sheet in new_sheets}
    draws: list[VariantDraw] = []
    new_groups = [_vary_group(group, by_id, config, draws) for group in manifest.identity_groups]
    return new_sheets, manifest.model_copy(update={"identity_groups": new_groups}), draws


def _vary_group(
    group: IdentityGroup,
    sheets_by_id: dict[str, SheetGraph],
    config: VariantConfig,
    draws: list[VariantDraw],
) -> IdentityGroup:
    if group.tag_variants:
        raise ValueError(
            f"expected exact reference tags for {group.tag!r} (split with exact_match_tags), "
            f"found tag_variants {group.tag_variants!r}"
        )
    variants: dict[str, str] = {}
    for reference_key in group.references:
        draw = _vary_reference(reference_key, group.tag, sheets_by_id, config)
        if draw is not None:
            draws.append(draw)
            variants[reference_key] = draw.variant_tag
    return group.model_copy(update={"tag_variants": variants})


def _vary_reference(
    reference_key: str,
    expected_tag: str,
    sheets_by_id: dict[str, SheetGraph],
    config: VariantConfig,
) -> VariantDraw | None:
    """Draw and apply a variant for one reference; None when the rate draw says leave it."""
    attributes = _reference_attributes(reference_key, expected_tag, sheets_by_id)
    # one stream per reference: other references, and the split itself, never shift this draw
    rng = random.Random(f"{config.seed}:{reference_key}")
    if rng.random() >= config.rate:
        return None
    family: Family = rng.choice(config.families)
    options = applicable_operators(family, expected_tag, str(attributes["node_class"]), rng)
    if not options:
        raise ValueError(f"no {family} operator applies to {expected_tag!r} ({reference_key})")
    operator, variant_tag = rng.choice(options)
    attributes["tag"] = variant_tag
    return VariantDraw(
        reference_key=reference_key,
        family=family,
        operator=operator,
        original_tag=expected_tag,
        variant_tag=variant_tag,
    )


def _reference_attributes(
    reference_key: str, expected_tag: str, sheets_by_id: dict[str, SheetGraph]
) -> dict[str, object]:
    """The mutable attribute dict of the reference node, checked to carry the exact tag."""
    sheet_id, _, node_id = reference_key.partition(":")
    sheet = sheets_by_id.get(sheet_id)
    if sheet is None or node_id not in sheet.graph:
        raise ValueError(f"expected reference {reference_key!r} on a known sheet, found none")
    attributes: dict[str, object] = sheet.graph.nodes[node_id]
    if attributes.get("tag") != expected_tag:
        raise ValueError(
            f"expected reference {reference_key!r} to carry tag {expected_tag!r}, "
            f"found {attributes.get('tag')!r}"
        )
    return attributes
