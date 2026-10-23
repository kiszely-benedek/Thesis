---
topic: Entitásfeloldás (entity resolution), megoldókulcs-szivárgás, oracle vs. végponttól végpontig mérés
status: draft
related: [ADR-0005, ADR-0009, ADR-0010, ADR-0013, docs/private/40-design/thesis-phase-plan.md, pid-lapkozi-csatlakozok.md, open100-csatlakozo-megoldokulcs.md]
---

# Entitásfeloldás és a megoldókulcs

## Miért létezik

Egy üzem P&ID-je nem egy rajz, hanem száz. Egy cső az 1. lapon kilép a lap szélén egy **off-page
connectorral** („folytatás a 2. lapon, OPC-4"), és a 2. lapon ugyanezzel a jelöléssel lép be. Ugyanaz a
szivattyú több lapon is megjelenhet, mindenhol a `P-101` taggel. Ha a lapokat külön-külön gráffá alakítod,
**száz szigeted** lesz, és a „honnan kapja a T-201 a folyadékot?" kérdésre nincs válasz, ha a forrás egy
másik lapon van.

Az **entitásfeloldás** (*entity resolution*, ER) az a lépés, ami a szigeteket egy üzemgráffá köti: eldönti,
melyik két csonk *ugyanaz a cső*, és melyik két csomópont *ugyanaz a berendezés*. A cím
„tudásgráf-építés" része nagyrészt ez.

## Az alapötlet

**Megoldókulcs (answer key / ground truth):** amikor mi vágjuk szét a generált üzemet lapokra, pontosan
tudjuk, melyik csonk melyikkel párban van. Ezt a `SplitManifest` tárolja (`ConnectorPair`,
`IdentityGroup`). Ez a vizsga megoldókulcsa.

**`rejoin()` ≠ resolver.** A `rejoin()` a megoldókulcsot olvassa, és visszaállítja az eredeti gráfot. Arra
jó, hogy bebizonyítsa: a vágás nem vesztett adatot (ez a *round-trip invariáns*, SMOKE-03). A **resolver**
ugyanezt csinálná **a megoldókulcs nélkül**, csak abból, ami a lapon látszik — pont úgy, ahogy egy mérnök
teszi, aki a rajzokat lapozza.

**Szivárgás (leakage):** ha a resolver bemenetébe véletlenül belekerül valami, ami a megoldókulcsból
származik, akkor „tökéletesen" teljesít — de nem oldott meg semmit, hanem puskázott. Nálunk ez konkrétan
megtörtént volna: a splitter ugyanazt a **node id**-t adja egy berendezés minden előfordulásának minden lapon
(`splitter.py:183`). Egy valódi rajzon nincs ilyen közös azonosító — az id a mi belső könyvelésünk.

**Helyességi kapu vs. eredmény.** A splitter alapbeállításain (`exact_match_tags=True`,
`connector_label_detail=FULL`) minden csonk kiírja a partnere számát, tehát a feloldás **konstrukció
szerint triviális**. Ha itt 100 %-ot kapunk, az nem eredmény, hanem csak annak igazolása, hogy a kód nem
hibás. **Eredmény** az, ami nehéz beállításon vagy valódi rajzon (OPEN100, 23 pár) jön ki.

**Oracle vs. végponttól végpontig.** A P4 skálázási kísérletnél a keresést mérjük. Ha a gráfot a resolver
rakja össze, és az hibázik, a keresés rossz eredményét nem tudjuk szétválasztani: a keresés volt gyenge,
vagy rossz gráfon keresett? Ezért kétféle futás létezik:
- **oracle**: a keresés a *tökéletes* (megoldókulcsból épített) gráfon fut — csak a keresést méri;
- **végponttól végpontig (end-to-end)**: a resolver gráfján — a teljes rendszert méri.

Az ADR-0010 szerint a P4 a resolver gráfján fut, és ha az nem egyezik az oracle-lel, mindkettőt jelentjük.

## Kidolgozott példa

Két lap, egy elvágott cső. Egy „csaló" resolver id alapján párosít, egy tisztességes a felirat alapján.
Utána **átnevezési tesztet** futtatunk: a lapon belüli id-k önkényesek, tehát átnevezésük nem változtathat az
eredményen — ha mégis, a resolver szivárgó adatot használt.

```python
sheet_1 = {"stubs": [{"id": "n7", "label": "OPC-3", "to_drawing": "S2", "to_connector": "OPC-4"}]}
sheet_2 = {"stubs": [{"id": "n7", "label": "OPC-4", "to_drawing": "S1", "to_connector": "OPC-3"}]}

def cheating_resolver(a, b):
    return [(x["label"], y["label"]) for x in a["stubs"] for y in b["stubs"] if x["id"] == y["id"]]

def label_resolver(a, b, a_name="S1", b_name="S2"):
    return [(x["label"], y["label"]) for x in a["stubs"] for y in b["stubs"]
            if x["to_drawing"] == b_name and x["to_connector"] == y["label"]
            and y["to_drawing"] == a_name and y["to_connector"] == x["label"]]

print(cheating_resolver(sheet_1, sheet_2), label_resolver(sheet_1, sheet_2))
sheet_2["stubs"][0]["id"] = "q1"   # átnevezési teszt
print(cheating_resolver(sheet_1, sheet_2), label_resolver(sheet_1, sheet_2))
```

Futtatva (2026-09-25):

```
[('OPC-3', 'OPC-4')] [('OPC-3', 'OPC-4')]
[] [('OPC-3', 'OPC-4')]
```

Átnevezés előtt **mindkettő tökéletes** — ebből nem látszik, hogy az egyik puskázik. Az átnevezés után a
csaló eltűnik. Ezért kell a resolver tervébe egy ilyen teszt (ADR-0009, „contract rule").

## Hol illeszkedik

- **P2 (KG-építés):** a vékony resolver itt készül, a `resolve(split(plant)) == plant` kapuval, megoldókulcs
  nélkül és átnevezési teszttel.
- **P5 (ER kiértékelés, EXP-0004):** precision/recall az OPEN100 23 visszatartott párján (ADR-0005: ezeket
  fejlesztéshez soha nem használjuk), és a splitter nehézségi tárcsáival (`exact_match_tags=False`, kisebb
  `connector_label_detail`) generált korpuszon.
- **Precision / recall** röviden: a precision azt mondja, a resolver által talált párok közül hány helyes; a
  recall azt, hogy a valódi párok közül hányat talált meg. Egy óvatos resolver precision-je magas, recall-ja
  alacsony — és fordítva.

## Gyakori tévhitek

1. **„100 % a szintetikus adaton = kész vagyunk."** Az alapbeállításon a 100 % elvárt, nem eredmény.
2. **„A `rejoin()` már megoldja."** A megoldókulcsot olvassa; a valódi rendszernek nincs ilyenje.
3. **„23 pár elég egy precision/recall állításhoz."** Egy **pont**, nem görbe (ADR-0007 szóhasználata). Egy
   hibás pár is ~4 százalékpontot mozdít. Kis valós ellenőrzésnek jó, a görbét a szintetikus söprés adja.
4. **„Ha a teszt zöld, nincs szivárgás."** A zöld teszt csak azt bizonyítja, hogy *arra* nem szivárog, amit
   teszteltél. Hogy más mező (pl. egy attribútum) nem hordoz-e megoldókulcsot, azt a resolver tervében külön
   ellenőrizni kell — jelenleg **nincs ellenőrizve** (ADR-0009).

## Ha egyetlen dolgot olvasol el

Kapcsolódó, a saját projektünkre írt jegyzet: `docs/Notes/open100-csatlakozo-megoldokulcs.md` — az OPEN100
valódi csatlakozóinak megoldókulcsa, amin a P5 mér.
