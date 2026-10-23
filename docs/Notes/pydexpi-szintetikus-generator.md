---
topic: A pyDEXPI szintetikus P&ID-generátora — hogyan rak össze egy rajzot mintákból, és hová kerülnek benne a szabályok
status: draft
related: [ADR-0003, ADR-0004, ADR-0007, why-a-synthetic-benchmark.md, 40-design/splitter.md]
date: 2026-09-12
---

# A pyDEXPI szintetikus generátora

Minden állítás ebben a jegyzetben a telepített **pyDEXPI 1.2.0** forráskódjának
elolvasásából jön (2026-09-10 és 09-12). Ahol valami a mi tervezési javaslatunk,
és nem a pyDEXPI dokumentációja mondja, ott ezt külön jelzem.

## 0. Hol van a `generator.py`, és miért nem nyílt meg

A korábbi üzenetben `pydexpi\syndata\generator.py`-t írtam. Ez a **telepített
csomagon belüli** útvonal, nem a mi repónkban lévő fájl, ezért nem találtad.
A pyDEXPI még nincs a projekt függőségei között: egy ideiglenes környezetbe
telepítettem, csak hogy elolvassam a forrását.

Így nyithatod meg:

- **GitHubon (ajánlott, mindig elérhető):**
  https://github.com/process-intelligence-research/pyDEXPI/blob/master/pydexpi/syndata/generator.py
- **Helyben, a uv gyorsítótárában** (ez eltűnik, ha valaki kiüríti a uv cache-t):
  `C:\Users\Otthon\AppData\Local\uv\cache\archive-v0\jJShquHiNvdYGtaU4ctwg\Lib\site-packages\pydexpi\syndata\generator.py`
- **Később a projektben:** amikor a pyDEXPI adaptert megépítjük és a csomag bekerül
  a függőségek közé, a fájl itt lesz: `.venv\Lib\site-packages\pydexpi\syndata\generator.py`

A `generator.py` rövid, 202 sor. De egymagában keveset mond, mert a tényleges
döntéseket a `generator_function.py` hozza. Érdemes a kettőt együtt olvasni.

## 1. A nagy kép: legókockák

A pyDEXPI generátora **nem a semmiből talál ki** P&ID-t. Kész, kicsi rajzrészletekből
dolgozik, ezeket hívja **pattern**-nek (mintának), és ezeket ragasztja össze egyre
nagyobb egésszé.

Képzelj el legókockákat, amelyeknek csatlakozócsonkjaik vannak. Egy kocka lehet
például egy szivattyú a hozzá tartozó szelepekkel, és van egy nyitott bemenő és egy
nyitott kimenő csőcsonkja. A generátor fog egy kockát, keres rajta egy szabad csonkot,
hozzáilleszt egy másik kockát, és ezt addig ismétli, amíg el nem fogynak a szabad
csonkok, vagy el nem éri a lépésszám-korlátot.

A modul saját dokumentációja pontosan ezt mondja: a mintákat "a csatlakozó
interfészeiken keresztül kötik össze, egy generátorfüggvényben előre rögzített logika
szerint".

**Ebből következik a legfontosabb tény:** a kimenet pontosan annyira valószerű, mint
a minták, amelyekből összerakják. A pip csomag **egyetlen mintafájlt sem tartalmaz**
(a teljes telepített csomagot átnéztem: nulla nem-kód fájl).

**A GitHub-repóban viszont van egy példa-mintakönyvtár**, csak nem kerül bele a pip
csomagba. A `data/dexpi_sample_patterns/` mappában 10 eloszlás-mappa van: column,
compressor, feed, hxer, mixer, product, pump, reactor, reactor_feed, storage (ezt magam
ellenőriztem, 2026-09-12). A kutató szerint ezekben összesen **23 minta** van, AGPL-3.0
licenccel. Egyik sem tartalmazza a valódi mérnöki szabályokat: nincsenek műszerek, nincs
visszacsapó szelep, és egy szivattyú-minta egy csupasz szivattyú.

A kutató a kódból és a mintafájlokból arra is következtetett, hogy minden "középső"
mintának pontosan egy bemenete és egy kimenete van. Ha ez igaz, ezekből a mintákból
a véletlen generátor **csak láncot vagy egyetlen gyűrűt** tud építeni: elágazást és
segédrendszert nem. Ez következtetés, **még nem futtattuk le**. Ha igaz, a
mintakönyvtárat nekünk kell megírnunk.

## 2. A szereplők

| Osztály | Mi ez | Hasonlat |
|---|---|---|
| `Pattern` | egy rajzrészlet nyitott csatlakozókkal | egy legókocka |
| `Connector` | egy nyitott csatlakozási pont a mintán | egy csonk a kockán |
| `PatternDistribution` | minták súlyozott gyűjteménye | egy zsák kocka, amelyből egyesek gyakrabban jönnek |
| `GeneratorFunction` | eldönti, mi legyen a következő lépés | aki a kockákat választja |
| `CappingFunction` | a végén lezárja a megmaradt nyitott csonkokat | a vakdugók |
| `ConnectorRenamingConvention` | egyedi nevet ad a csatlakozóknak | a címkéző |
| `GenerationHistory` | feljegyzi az összes lépést | a jegyzőkönyv |
| `SyntheticPIDGenerator` | végrehajtja az egészet | a gép |

## 3. A ciklus lépésről lépésre

A `generate_pattern()` metódus pontosan ezt csinálja (a forrás sorrendjében):

1. **Visszaállítás** (`reset`): üres minta, lépésszámláló nullán, új jegyzőkönyv.
2. **Kezdőminta** (`initialize_pattern`): a generátorfüggvény választ egy kiinduló
   mintát. A `RandomGeneratorFunction` véletlenszerűen választ egy eloszlást, és
   abból mintát húz.
3. **Ciklus**, amíg mindhárom feltétel teljesül:
   - van még nyitott csatlakozó,
   - a lépésszám kisebb, mint `max_steps` (alapértéke **100**),
   - nem kért senki leállást.

   Minden körben a generátorfüggvény dönt a következő lépésről. Két fajta lépés van:
   - **belső kötés**: két csatlakozót köt össze *ugyanazon* a mintán belül, így jön
     létre egy visszacsatolt kör (recycle). Ennek valószínűsége a `p_connect_internal`,
     amelynek alapértéke **0.0**, vagyis alapból **soha nem történik meg**;
   - **új minta hozzáadása**: véletlen nyitott csatlakozó a meglévő rajzon → véletlen
     eloszlás → abból minta húzása a súlyok szerint → a mintán véletlen *kompatibilis*
     csatlakozó → a kettő összeillesztése.
4. **Lezárás** (`cap_connectors`): ha van `CappingFunction`, lezárja a megmaradt
   nyitott csonkokat.
5. **Visszaadja** a kész mintát.

Két apró, de fontos részlet:

- A `max_steps` **lépésszám-korlát, nem az üzem mérete.** A generálás hamarabb is
  leállhat, ha elfogynak a nyitott csatlakozók.
- Alapbeállítással nincs belső kötés, tehát **nincs visszacsatolt kör**. Valódi
  üzemekben viszont vannak visszaforgató ágak. Ha ilyet akarunk, a
  `p_connect_internal` értékét nekünk kell nulla fölé állítani.

## 4. Hol vannak a mérnöki szabályok? Alapból sehol

Ez a legfontosabb szakasz, és közvetlenül a kérdésedhez kapcsolódik: lehet-e a
generálást valódi szabályokra építeni.

**A generátor maga nem ismer P&ID-szabályokat.** A `RandomGeneratorFunction`
dokumentációja szó szerint azt írja, hogy a következő mintákat és csatlakozókat
"teljesen véletlenszerűen" választja.

**A csatlakozók kompatibilitása is csak irányt néz.** A DEXPI-mintáknál a bemenő
csővezeték-csatlakozó akkor fogad el egy párt, ha az kimenő, és fordítva. A kód
szó szerint ennyi:

```python
return isinstance(counterpart, BasicPipingOutConnector)
```

Semmi több. A generátor tehát bármilyen kimenetet bármilyen bemenethez hozzáköthet,
mindegy, milyen berendezés van a két végén.

Így három helyen kerülhetnek szabályok a rendszerbe. A pyDEXPI-nek mindhárom a
**kiterjesztési pontja**, azt viszont, hogy melyik szabály hová való, már **mi
javasoljuk**:

| Hová | Milyen szabály fér bele | Példa |
|---|---|---|
| **A mintákba** | helyi elrendezés, egy berendezésen belül | egy szivattyú a saját elzáró- és visszacsapó szelepével, egyetlen mintaként |
| **A kompatibilitás-ellenőrzésbe** (`Connector.assess_valid_counterpart` felülírása) | mi köthető mihez | hűtővíz-vezeték ne csatlakozzon közvetlenül egy reaktortartályhoz |
| **Saját `GeneratorFunction`-be** | az egész üzem összetétele | előbb a fő technológiai lánc, aztán a segédrendszerek, adott arányban |

Van egy **negyedik** hely is, amelyet a kutatás talált: a `CappingFunction`. Ez a
generálás végén zárja le a nyitva maradt csatlakozókat, így ide illeszthető például az a
szabály, hogy a segédrendszer-csonkok (hűtővíz be/vissza) szolgáltatás-címkével záruljanak.

Hogy a szabványok és a szakirodalom milyen szabályokat írnak le, és melyik a négy hely
közül melyikbe illeszthető, azt a kész kutatás gyűjti össze:
`10-literature/pid-structural-rules.md` (angol, forrásokkal) és
`docs/Notes/pid-szerkezeti-szabalyok.md` (magyar tanító jegyzet).

## 5. Reprodukálhatóság: vigyázni kell

A saját `splitter`-ünk szigorú szabályt követ: minden véletlen döntés egyetlen,
seeddel indított `random.Random(seed)` példányon megy át, és a globális `random`
modult sosem érinti. Így ugyanaz a seed mindig bájtra azonos eredményt ad.

**A pyDEXPI nem így működik.** A modul szintű `random` függvényeket hívja
(`random.choice`, `random.choices`, `randint`), és nincs seed paramétere. Ennek két
következménye van:

- Ugyanazt a rajzot csak úgy kaphatod meg újra, ha generálás előtt beállítod a
  **globális** véletlenszám-generátort (`random.seed(n)`). Ez a program minden más
  részére is hat, amely a globális `random`-ot használja.
- Az adapter, amely a pyDEXPI-t becsomagolja, ezt el kell rejtse: seed beállítása,
  generálás, majd a korábbi állapot visszaállítása. Ez az adapter tervének egyik pontja
  lesz.

Van egy második út is: a `GenerationHistory` feljegyzi a lépéseket, és a
`ReconstructionGeneratorFunction` a kód szerint "a jegyzőkönyv alapján dönti el a
következő lépést". Egy generálás tehát a jegyzőkönyvéből újrajátszható. Hogy ez
nagy mintakönyvtárnál gyakorlatban mennyire megbízható, azt még **nem próbáltuk ki**.

## 6. Irány — ez rendben van

A gráffá alakító `GraphLoader` **irányított** gráfot ad (`nx.MultiDiGraph`).
A `PipingNetworkSegment.flowDirection` mező értéke `null`, `single flow` vagy
`dual flow` lehet: azt mondja meg, egyirányú-e egy csőszakasz, vagy mindkét irányba
folyhat benne az anyag. Magát az irányt a szakasz forrása → célja adja. Ez fontos,
mert a PID2Graph mind a 762 gráfja **irányítatlan**, a pyDEXPI-ből generált gráfok
viszont már eleve irányítottak.

**Még nem futtattuk végig:** mintakönyvtár nélkül egyetlen modellt sem generáltunk,
így generált gráfot sem vizsgáltunk meg. Ez az adapter első feladata.

## 7. Tévhitek, amiket érdemes elkerülni

**"A pyDEXPI ismeri a P&ID-szabályokat."** Nem. A csatlakozók kompatibilitásán
(be- vagy kimenő) túl semmit nem ellenőriz. A szabályokat a mintákba, a
kompatibilitás-ellenőrzésbe és a generátorfüggvénybe nekünk kell beleírni.

**"Végtelen adat = valószerű adat."** A generátor bármennyi rajzot előállít, de
mindegyik ugyanazokból a mintákból épül. Tízezer rajz rossz mintákból tízezer rossz
rajz. A mennyiség a skálát adja, a valószerűséget a minták adják.

**"A `max_steps` az üzem mérete."** Nem, az csak egy felső korlát a lépésszámra.
A tényleges méretet a minták mérete, a csatlakozók száma és a lezárás együtt határozza
meg.

**"A pyDEXPI több lapos rajzsorozatot generál."** Nem, egyetlen modellt állít elő.
A DEXPI-ben egy `DexpiModel` egy rajznak felel meg (lásd `ontologia-pid.md`). A lapokra
bontást, a lapközi csatlakozókat és a megoldókulcsot a **mi `splitter`-ünk** végzi,
ezért volt rá szükség.

**"Ha ugyanazt a seedet adom, ugyanazt kapom."** Csak akkor, ha a globális
`random`-ot állítod be, és közben semmi más nem nyúl hozzá. A pyDEXPI-nek nincs saját
seed paramétere.
