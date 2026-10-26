---
topic: A rajztól a gráfig — pyDEXPI-osztályok, motor mint alkatrész, elektromos működtetés, jelutak (szabályozókör, kaszkád, reteszelés)
status: draft
date: 2026-10-26
related: [valos-pid-felepites.md, pydexpi-szintetikus-generator.md, ontologia-pid.md, ADR-0057, ADR-0058, 40-design/generator-v2-pid-vocabulary.md]
---

# A rajztól a gráfig: hogyan lesz egy P&ID-részletből pyDEXPI-modell és tudásgráf

Az ISA-betűket és a szabványos csőkialakításokat (miért van ott az a szelep) a `valos-pid-felepites.md` magyarázza.
Ez a jegyzet a következő lépés: **hogyan írja le ugyanezt a gép**, vagyis milyen pyDEXPI-osztály lesz egy
szimbólumból, és milyen élek lesznek a gráfunkban.

## Miért létezik

Egy P&ID-n háromféle vonal fut: **csővezeték** (anyag folyik benne), **jelvezeték** (szaggatott: információ folyik
benne) és a kettőt összekötő **mérési pont** (egy műszer „ráül” egy csőre vagy tartályra). Ember számára ez egy kép.
Egy kérdésre válaszoló rendszernek viszont tudnia kell, hogy *mi szabályoz mit*, *mi mér mit*, *mi áll le, ha a szint
túl magas*. Ehhez a képből **típusos elemek és típusos kapcsolatok** kellenek. A DEXPI szabvány ezt adja meg (a
pyDEXPI a Python-megvalósítása), a mi gráfsémánk pedig ebből vezeti le a csomópontokat és az éleket (ADR-0058:
egyetlen ősosztály-szabály az engedélyezett osztálylistán).

## Az alapötlet

**1. Három nagy család.** A pyDEXPI 1.2.0 öröklési lánca (lefuttatva, `__mro__`):

| Rajzon | pyDEXPI-osztály | Ősei |
|---|---|---|
| szivattyú | `CentrifugalPump` | `Pump` → `Equipment` → `TaggedPlantItem` |
| tartály | `Tank` | `Vessel` → `Equipment` |
| golyóscsap (pl. XV) | `BallValve` | `OperatedValve` → `PipingComponent` |
| visszacsapó szelep | `SwingCheckValve` | `CheckValve` → `PipingComponent` |
| T-idom | `PipeTee` | `PipeFitting` → `PipingComponent` |
| biztonsági szelep | `SpringLoadedGlobeSafetyValve` | `SafetyValveOrFitting` → `PipingComponent` |
| távadó (PT, LT…) | `ProcessSignalGeneratingFunction` | nem berendezés, nem csőelem: *funkció* |
| kijelző / kapcsoló buborék (PI, LSHH) | `ProcessInstrumentationFunction` | funkció |
| szabályozó (PIC, FIC) | `ProcessControlFunction` | `ProcessInstrumentationFunction` |
| szelepműködtető | `ActuatingFunction` | funkció |
| elektromos indítás / frekvenciaváltó | `ActuatingElectricalFunction` | funkció |

A műszerek tehát **funkciók**, nem tárgyak. A DEXPI azt modellezi, hogy *mit csinál* a jel (mér, kijelez, szabályoz,
működtet), nem azt, hogy milyen dobozban van. Ezért nincs külön „Rosemount 3051” osztály. Az, hogy a PT-1041 mögött
melyik gyártó készüléke áll, a műszerlista dolga (ez a közös projekt összekötő rétege, plantkg ADR-0002).

**2. A motor alkatrész, nem csomópont.** A pyDEXPI-ben a szivattyúnak `motors` mezője van, benne egy
`AlternatingCurrentMotorAsComponent`. Ez a gép *része*, ahogy a rajzon is a szivattyú szimbólumához tapad. Saját
altagje van: a `P-151` motorja `PM-151`. A gráfunkban ezért nem lesz belőle külön csomópont.

**3. A gép elektromos működtetése.** Egy szelepet egy `ActuatingFunction` mozgat (pneumatika, mágnesszelep). Egy
gépet viszont villamos jel indít vagy állít fordulatszámra: ezt az `ActuatingElectricalFunction` (AEF) modellezi.
A sémában **csak AEF vezérelhet gépet** (`validation.py`, pár-szabály), szelepet pedig csak a sima működtető.

**4. A gráf élei.** A sémánk topológiai élei (a `related_to` tartalék nélkül):

| Él | Jelentés | Példa |
|---|---|---|
| `send_to` | anyag folyik | tartály → szelep → szivattyú |
| `measured_by` | ezt méri ez a műszer | `TK-101 -measured_by-> LT-1030` |
| `send_signal_to` | jel megy | `LT-1030 -> LSHH-1030` |
| `control` | ez mozgatja azt | működtető `-control->` `XV-1030` |
| `has_agitator` | keverő a tartályban | `tartály -> keverőmű` |

A **jelút** így mindig ugyanaz a minta: *mérés → (döntés) → működtetés → beavatkozás*.

| Jelút | Láncolat |
|---|---|
| szabályozókör | `FE/PT → FIC/PIC → működtető → FV/PV` (közös hurokszám) |
| leállító reteszelés | `LT → LSHH → működtető → XV` (+ `XY` mágnesszelep, `ZSO/ZSC` végállás) |
| kézi indítás | `HS → AEF → szivattyú` (+ `YI` üzemjelzés) |
| fordulatszám-szabályozás | `PT → PIC → AEF → szivattyú` |
| kaszkád | `LT → LIC` alapjelet ad egy `FIC`-nek, és csak a `FIC` mozgat szelepet |

## Kidolgozott példa (lefuttatva 2026-10-26, a repó v2-építőjével)

Két mintaterv a `tests/v2_micro_plans.py`-ból (`speed_control`, `trip`). Mindkettő a DEXPI-építőn és az adapteren
ment át (`DexpiPlantBuilderV2` → `plant_graph_v2`). Ezek a jelutas élek jöttek ki (`-` = tag nélküli elem):

```text
== speed_control  (változó fordulatszámú szivattyú)
  V-101(PressureVessel)            -measured_by->    PT-1041(ProcessSignalGeneratingFunction)
  PT-1041                           -send_signal_to-> PIC-1041(ProcessControlFunction)
  PIC-1041                          -send_signal_to-> -(ActuatingElectricalFunction)
  -(ActuatingElectricalFunction)    -control->        P-151(CentrifugalPump)
  P-151 motorja: AlternatingCurrentMotorAsComponent, altag PM-151

== trip  (magas szint miatti leállítás)
  TK-101(Tank)                      -measured_by->    LT-1030(ProcessSignalGeneratingFunction)
  LT-1030                           -send_signal_to-> LSHH-1030(ProcessInstrumentationFunction)
  LSHH-1030                         -send_signal_to-> -(ActuatingFunction)
  -(ActuatingFunction)              -control->        XV-1030(BallValve)
  XV-1030(BallValve)                -measured_by->    ZSO-1030(ProcessSignalGeneratingFunction)
```

Kiolvasva: „ha a TK-101 szintje nagyon magas, az LSHH-1030 a működtetőn át **lezárja** az XV-1030-at, és a
ZSO-1030 visszajelzi, hogy a szelep nyitva van-e”. Ez egy gráfbejárás: a `TK-101`-ből `measured_by`, aztán
`send_signal_to`-k, végül `control`. Ilyen kérdést a rendszerünknek több lapon át is meg kell tudnia válaszolni.

Saját magad is lefuttathatod (a repó gyökeréből):

```python
import sys; sys.path.insert(0, "tests")
from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.benchmark.v2.plan_models import GenerationRecordV2
from v2_micro_plans import CONSTRUCT_PLANS, plan_base

b = DexpiPlantBuilderV2("plant0"); plan_base(b); CONSTRUCT_PLANS["trip"](b)
rec = GenerationRecordV2(plant_id="plant0", seed=0, generator_config="{}", pydexpi_version="t")
g = plant_graph_v2(b.build(), rec)[0]
for s, t, d in g.edges(data=True):
    print(g.nodes[s].get("tag"), d["relation"], g.nodes[t].get("tag"))
```

## Hol illeszkedik

- **Generátor v2** (ADR-0057, ADR-0058). A T7-es csőkialakítások és a T8-as műszerminták pontosan ezeket a
  láncolatokat rakják le, a DEXPI-modellben és a gráf-orákulumban egyszerre. A tesztek ellenőrzik, hogy a kettő
  csomópontra és élre megegyezik.
- **Valódi fájl betöltése** (`--vocabulary v2`, T6). Egy valódi DEXPI-fájl ugyanezekre az osztályokra és élekre
  képződik le.
- **Közös projekt.** A PT, a szabályzószelep, az XV és a szivattyú az a négy fajta, amelyhez Zsombor adatlapjai
  kapcsolódnak (plantkg ADR-0002).
- **Amit szándékosan nem modellezünk.** A villamos hálózatot (`ActuatingElectricalSystem`) és a motor adatait nem
  építjük fel (ADR-0021: nincs berendezésadat). Az `InstrumentationLoopFunction` sem épül fel: a hurkot a közös
  hurokszám köti össze.

## Gyakori tévhitek

1. **„A műszer egy tárgy a csövön.”** A DEXPI-ben funkció. Egy PDT-nek két csatlakozása van a valóságban, a modellben
   viszont egy távadónak csak egy mérési pontja lehet, ezért a generátor csak az egyik oldalát rajzolja.
2. **„A `measured_by` a műszertől mutat a tartály felé.”** Fordítva: `tartály -measured_by-> LT`. Az él iránya azt
   mondja, hogy „ezt az elemet méri”, nem azt, hogy „ez mér”.
3. **„A motor külön berendezés.”** Alkatrész, saját altaggel (`PM-151`), csomópont nélkül.
4. **„A kaszkád az a kaszkád.”** A `kaszkad-onjelzes.md` kaszkádja a *lekérdezési* módszerek sorrendje a
   kérdés-válasz rendszerben. Itt a kaszkád *szabályozási* fogalom: egy szabályozó egy másiknak ad alapjelet.
   Két teljesen különböző dolog ugyanazzal a szóval.
5. **„Minden szelep egyforma.”** Az FV *szabályoz* (folyamatosan állít). Az XV *nyit vagy zár*, és leállításnál
   zár. A visszacsapó szelepet (`CheckValve`) semmi nem működteti, maga az áramlás nyitja.
6. **„A csőosztály-váltás egy csőelem, amin lehet mérni.”** A `PropertyBreak` öröklési láncában nincs
   `PipingComponent`, és a pyDEXPI nem fogadja el mérési helyként (próba, T6). A vezetékszám a váltás után megváltozik
   (T8).

## Ha egyetlen dolgot olvasol

A pyDEXPI repója és dokumentációja, főleg az osztálymodell:
<https://github.com/process-intelligence-research/pyDEXPI>
