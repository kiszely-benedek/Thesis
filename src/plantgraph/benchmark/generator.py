"""A szintetikus üzemgráf topológiájának megtervezése (`plant-generator.md` §3.3).

Ez a modul **csak a topológiát dönti el**: melyik berendezés melyik egységbe
kerül, melyik kettő közt fut csővezeték, hol van benne szelep, melyik
berendezést szabályozza melyik szelep. A tényleges gráf vagy DEXPI-modell
felépítését egy `PlantBuilder` végzi (`generator_models.py`) — ez a modul
csak sztringeket, egész és lebegőpontos számokat ad át neki, pyDEXPI-t
sosem importál (`plant-generator.md`, "Offline split of step 3": a pyDEXPI
csomag ezen a gépen nem telepíthető, ezért a topológia-tervezés és a
DEXPI-építés két külön lépésre vált szét).

A `plan_plant` egyetlen belépési pont. Minden véletlen döntés egy
`random.Random(config.seed)`-en megy át — sosem a globális `random` modulon,
és sosem `set`-en való bejáráson —, hogy ugyanaz a seed mindig ugyanazt a
gráfot adja (`plant-generator.md` invariáns 3, 4).
"""

from __future__ import annotations

import random

from plantgraph.benchmark.generator_models import (
    GenerationRecord,
    GeneratorConfig,
    LoopSpec,
    PlantBuilder,
    StreamKind,
    ValveSpec,
)
from plantgraph.graph.schema import CLASS_SPECS, OPERATED_VALVE_CLASSES, VALVE_CLASSES, NodeClass


def plan_plant(config: GeneratorConfig, builder: PlantBuilder) -> GenerationRecord:
    """Megtervezi egy üzem topológiáját a `config` szerint, és felépítteti a `builder`-rel.

    Az öt lépés sorrendje maga a specifikáció (`plant-generator.md` §3.3):
    egységek, berendezés, egységen belüli áramok, egységek közti áramok,
    szabályozókörök.
    """
    state = _GenerationState(config, builder)
    state.add_sections()
    state.add_equipment()
    state.add_intra_unit_streams()
    state.add_inter_unit_streams()
    state.add_control_loops()
    return state.record()


class _GenerationState:
    """`plan_plant` belső, nem publikus állapota: számlálók és a köztes eredmények.

    Azért osztály, hogy az öt lépés (§3.3) névvel ellátott metódusokban
    éljen egy hosszú függvény helyett, közös állapoton osztozva.
    """

    def __init__(self, config: GeneratorConfig, builder: PlantBuilder) -> None:
        self.config = config
        self.builder = builder
        self.rng = random.Random(config.seed)

        #: line_number -> honnan ered az adott csővezeték (a GenerationRecord anyaga)
        self.stream_kind: dict[str, StreamKind] = {}
        #: units_equipment[egység indexe] = az egység berendezés node_id-jai, felvétel sorrendben
        self.units_equipment: list[list[str]] = []
        #: bármely eddig felvett berendezés node_id-ja -> az egység sorszáma (1-től) —
        #: a szelepek és a szabályozókörök ebből tudják, melyik egységhez tartoznak
        self.node_unit: dict[str, int] = {}
        #: eddig felvett csővezetékek (forrás, cél) rendezett párként —
        #: a duplikátum- és a recycle-ellenőrzés erre épül
        self.stream_pairs: set[tuple[str, str]] = set()
        #: berendezés node_id -> a kimenő csővezetékein lévő szelepek, felvétel sorrendjében
        #: (szabályozókör-jelölt csak ezek közül kerülhet ki, §3.3 lépés 5)
        self.valves_by_source: dict[str, list[ValveSpec]] = {}
        #: már szabályozott szelepek node_id-ja — egy szelepen legfeljebb egy kör ülhet
        self.controlled_valves: set[str] = set()

        self._node_seq: dict[tuple[int, str], int] = {}
        self._tag_seq: dict[tuple[int, str], int] = {}
        self._loop_no: dict[int, int] = {}
        self._stream_seq = 0

    # ---- lépés 0: egységek --------------------------------------------------------------

    def add_sections(self) -> None:
        """Minden technológiai egységet létrehoz, mielőtt bármi mást felvennénk beléjük."""
        for unit_index in range(self.config.n_units):
            self.builder.add_section(unit_no=unit_index + 1)

    # ---- lépés 1: berendezés ------------------------------------------------------------

    def add_equipment(self) -> None:
        """Minden egységbe egyenletes eloszlású darabszámú, súlyozva választott berendezést tesz."""
        weighted_classes = sorted(self.config.equipment_weights)
        weights = [self.config.equipment_weights[name] for name in weighted_classes]
        for unit_index in range(self.config.n_units):
            unit_no = unit_index + 1
            count = self.rng.randint(
                self.config.equipment_per_unit_min, self.config.equipment_per_unit_max
            )
            equipment_ids: list[str] = []
            for _ in range(count):
                equipment_ids.append(self._add_one_equipment(unit_no, weighted_classes, weights))
            self.units_equipment.append(equipment_ids)

    def _add_one_equipment(
        self, unit_no: int, weighted_classes: list[str], weights: list[float]
    ) -> str:
        """Felvesz egy berendezést: sorsol egy osztályt, id-t/tag-et gyárt, beküldi a buildernek."""
        node_class = self.rng.choices(weighted_classes, weights)[0]
        node_id = self._next_node_id(unit_no, "eq")
        tag, tag_prefix, tag_seq = self._next_tag(unit_no, node_class)
        self.builder.add_equipment(
            node_id=node_id,
            node_class=node_class,
            unit_no=unit_no,
            tag=tag,
            tag_prefix=tag_prefix,
            tag_seq=tag_seq,
            data={},  # equipment_data egyelőre figyelmen kívül marad, lásd generator_models.py
        )
        self.node_unit[node_id] = unit_no
        return node_id

    # ---- lépés 2: egységen belüli áramok (véletlen fa + recycle) -------------------------

    def add_intra_unit_streams(self) -> None:
        """Minden egységben véletlen fát épít, majd eséllyel egy recycle-áramot ad hozzá."""
        for equipment_ids in self.units_equipment:
            tree_parent = self._add_tree(equipment_ids)
            self._maybe_add_recycle(equipment_ids, tree_parent)

    def _add_tree(self, equipment_ids: list[str]) -> dict[int, int]:
        """Véletlen rekurzív fa: minden csomópont szülője egy korábbi, véletlen csomópont."""
        tree_parent: dict[int, int] = {}
        for child_index in range(1, len(equipment_ids)):
            parent_index = self.rng.randrange(child_index)
            tree_parent[child_index] = parent_index
            self._add_stream(
                equipment_ids[parent_index], equipment_ids[child_index], StreamKind.TREE
            )
        return tree_parent

    def _maybe_add_recycle(self, equipment_ids: list[str], tree_parent: dict[int, int]) -> None:
        """Eséllyel egy visszafelé mutató (recycle) áramot ad az egységen belül."""
        if self.rng.random() >= self.config.p_recycle:
            return
        candidates = self._recycle_candidates(equipment_ids, tree_parent)
        if not candidates:
            return
        src_id, dst_id = self.rng.choice(candidates)
        self._add_stream(src_id, dst_id, StreamKind.RECYCLE)

    def _recycle_candidates(
        self, equipment_ids: list[str], tree_parent: dict[int, int]
    ) -> list[tuple[str, str]]:
        """A lehetséges recycle-párok: korábbi, nem szülő berendezés, ha még nincs köztük áram."""
        candidates: list[tuple[str, str]] = []
        for src_index in range(len(equipment_ids)):
            for dst_index in range(1, src_index):
                if tree_parent.get(src_index) == dst_index:
                    continue
                src_id, dst_id = equipment_ids[src_index], equipment_ids[dst_index]
                if not self._has_stream(src_id, dst_id):
                    candidates.append((src_id, dst_id))
        return candidates

    def _has_stream(self, a: str, b: str) -> bool:
        """Igaz, ha bármelyik irányban már fut csővezeték a és b között."""
        return (a, b) in self.stream_pairs or (b, a) in self.stream_pairs

    # ---- lépés 3: egységek közti áramok (kötelező + eséllyel keresztkötés) ----------------

    def add_inter_unit_streams(self) -> None:
        """Minden egységet (az elsőt kivéve) összeköt egy korábbival, eséllyel keresztkötéssel."""
        for unit_index in range(1, self.config.n_units):
            self._add_cross_unit_stream(unit_index)
            self._maybe_add_cross_link(unit_index)

    def _add_cross_unit_stream(self, unit_index: int) -> None:
        """A kötelező áram: egy korábbi egység egy berendezéséből ide, az első berendezésbe."""
        upstream_index = self.rng.randrange(unit_index)
        src_id = self.rng.choice(self.units_equipment[upstream_index])
        dst_id = self.units_equipment[unit_index][0]
        self._add_stream(src_id, dst_id, StreamKind.CROSS_UNIT)

    def _maybe_add_cross_link(self, unit_index: int) -> None:
        """Eséllyel egy plusz áramot ad egy korábbi egységből ide, egy nem-első berendezésbe."""
        equipment_ids = self.units_equipment[unit_index]
        # a rng.random() mindig lefut, a hossz-feltétel sosem fogyaszt véletlent —
        # ez tartja a hívási sorrendet azonosnak, függetlenül az egység méretétől
        if self.rng.random() >= self.config.p_cross_link or len(equipment_ids) <= 1:
            return
        source_unit_index = self.rng.randrange(unit_index)
        src_id = self.rng.choice(self.units_equipment[source_unit_index])
        dst_id = self.rng.choice(equipment_ids[1:])
        if (src_id, dst_id) not in self.stream_pairs:
            self._add_stream(src_id, dst_id, StreamKind.CROSS_LINK)

    # ---- lépés 4: egy csővezeték felvétele (minden áram ezen megy át) --------------------

    def _add_stream(self, src_id: str, dst_id: str, kind: StreamKind) -> None:
        """Felvesz egy csővezetéket a rajta lévő szelepekkel, és megjegyzi, honnan eredt.

        Raises:
            ValueError: ha erre a rendezett (forrás, cél) párra már fut csővezeték.
        """
        if (src_id, dst_id) in self.stream_pairs:
            raise ValueError(
                f"duplicate stream {src_id} -> {dst_id}; "
                "a stream already exists on this ordered pair"
            )
        fluid_code = self.rng.choice(self.config.fluid_codes)
        self._stream_seq += 1
        line_number = f"{fluid_code}-{self._stream_seq}"
        valves = self._add_valves(src_id)

        self.builder.add_stream(
            line_number=line_number,
            fluid_code=fluid_code,
            src_id=src_id,
            dst_id=dst_id,
            valves=valves,
        )

        self.stream_pairs.add((src_id, dst_id))
        self.stream_kind[line_number] = kind
        self.valves_by_source.setdefault(src_id, []).extend(valves)

    def _add_valves(self, src_id: str) -> list[ValveSpec]:
        """A csővezetékbe eső szelepeket gyártja le, a forrás egységéhez kötve (§3.3 lépés 4)."""
        unit_no = self.node_unit[src_id]
        valve_count = self.rng.randint(0, self.config.valves_per_stream_max)
        valves: list[ValveSpec] = []
        for _ in range(valve_count):
            node_class = self.rng.choice(sorted(VALVE_CLASSES))
            node_id = self._next_node_id(unit_no, "va")
            tag, _, _ = self._next_tag(unit_no, node_class)
            valves.append(ValveSpec(node_id=node_id, node_class=node_class, tag=tag))
        return valves

    # ---- lépés 5: szabályozókörök ---------------------------------------------------------

    def add_control_loops(self) -> None:
        """Minden berendezéshez, csomópont-azonosító sorrendben, eséllyel szabályozókört rendel."""
        all_equipment = sorted(
            equipment_id for unit in self.units_equipment for equipment_id in unit
        )
        for equipment_id in all_equipment:
            self._maybe_add_control_loop(equipment_id)

    def _maybe_add_control_loop(self, equipment_id: str) -> None:
        """Eséllyel szabályozókört tesz egy még nem szabályozott, avatkozásra alkalmas szelepére."""
        if self.rng.random() >= self.config.p_control_loop:
            return
        candidates = [
            valve
            for valve in self.valves_by_source.get(equipment_id, [])
            if valve.node_class in OPERATED_VALVE_CLASSES
            and valve.node_id not in self.controlled_valves
        ]
        if not candidates:
            return

        valve = self.rng.choice(candidates)
        variable = self.rng.choice("FLPT")
        unit_no = self.node_unit[equipment_id]
        loop = LoopSpec(
            equipment_id=equipment_id,
            valve_id=valve.node_id,
            variable=variable,
            unit_no=unit_no,
            loop_no=self._next_loop_no(unit_no),
            # a sorrend (PSGF, PIF, AF) számít: az "in" számláló ebben a sorrendben nő
            psgf_id=self._next_node_id(unit_no, "in"),
            pif_id=self._next_node_id(unit_no, "in"),
            af_id=self._next_node_id(unit_no, "in"),
        )
        self.builder.add_control_loop(loop)
        self.controlled_valves.add(valve.node_id)

    # ---- azonosító- és tag-gyártás (§3.3 "Ids and tags") ----------------------------------

    def _next_node_id(self, unit_no: int, kind: str) -> str:
        """Új csomópont-id: `{plant_id}-u{unit_no}-{kind}{seq}`, `seq` (egység, kind) szerint nő."""
        key = (unit_no, kind)
        seq = self._node_seq.get(key, 0) + 1
        self._node_seq[key] = seq
        return f"{self.config.plant_id}-u{unit_no}-{kind}{seq}"

    def _next_tag(self, unit_no: int, node_class: str) -> tuple[str, str, int]:
        """Berendezés/szelep tag-je: `{prefix}-{unit_no}-{seq}`, `seq` (egység, prefix) szerint."""
        prefix = CLASS_SPECS[NodeClass(node_class)].tag_prefix
        if prefix is None:
            raise ValueError(f"node_class {node_class!r} has no tag_prefix in schema.CLASS_SPECS")
        key = (unit_no, prefix)
        seq = self._tag_seq.get(key, 0) + 1
        self._tag_seq[key] = seq
        return f"{prefix}-{unit_no}-{seq}", prefix, seq

    def _next_loop_no(self, unit_no: int) -> int:
        """A szabályozókör-sorszám ("s" a §3.3-ban), egységenként külön számlálva."""
        loop_no = self._loop_no.get(unit_no, 0) + 1
        self._loop_no[unit_no] = loop_no
        return loop_no

    # ---- eredmény ---------------------------------------------------------------------

    def record(self) -> GenerationRecord:
        """A lefutott generálás megoldókulcsa: a config, a seed és minden áram eredete."""
        return GenerationRecord(
            plant_id=self.config.plant_id,
            seed=self.config.seed,
            generator_config=self.config.model_dump_json(),
            pydexpi_version=self.builder.backend_version,
            stream_kind=self.stream_kind,
        )
