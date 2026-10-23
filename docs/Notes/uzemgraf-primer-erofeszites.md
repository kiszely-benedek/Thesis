# Üzemgráf a promptban, P&ID-alapismeretek, gondolkodási erőfeszítés, párhuzamos hívások

*Tanulási jegyzet, 2026-10-03. Háttér: ADR-0039…0043 és a `40-design/plant-graph-first-and-effort-routing.md` terv.*

## 1. Miért bukott el a T-11-1 kérdés, ha minden adat a promptban volt?

A kérdés: „Mely berendezések és szelepek kapnak közvetlenül anyagot a T-11-1-ből?" A helyes válasz két
visszacsapó szelep (CHV-11-3, CHV-11-2). Mindkét modell (GLM és Sonnet) üres listát adott.

Az ok a **rajzolt (előfordulás-) gráfban** van. A T-11-1 a 4. lapon van, a két szelep az 5. lapon. A rajzon a cső a
lap szélén egy **lapközi csatlakozóban** (off-page connector) végződik, és a másik lapon egy párjából folytatódik.
A gráfban ez így néz ki:

```
T-11-1 --send_to--> [kimenő csatlakozó, 4. lap] --continues_as--> [bejövő csatlakozó, 5. lap] --send_to--> CHV-11-3
```

Szó szerint olvasva a T-11-1-nek csak csatlakozó-szomszédai vannak, berendezés-szomszédja nincs. A közös válasz-prompt
ráadásul sehol nem magyarázza el, mit jelent a `continues_as`. (A CypherRAG lekérdezés-író lépése megkapja ezt a
magyarázatot, a többi stratégia nem.)

Az **üzemgráfban** (az egyesített gráfban) a csatlakozópárok már össze vannak kötve, így ugyanez egyetlen él:
`T-11-1 --send_to--> CHV-11-3`. A tétel lapjai egy `sheets` tulajdonságban szerepelnek. Ezért döntöttünk úgy, hogy a
Hierarchical és a kérdésfüggő változata is az üzemgráfból építse a kontextust. A lapválasztás nem változik, csak az,
hogy mit írunk ki belőle. Így a két változat különbsége tisztán a gráfábrázolás hatása.

## 2. Miért nem a visszacsapó szelepet kell elzárni?

Kérdés: „Mely szelepeket kell elzárni, hogy a P-3-1-et leválasszuk minden előtte lévő berendezéstől?" Mindkét modell
a CHV-3-1 visszacsapó szelepet nevezte meg.

- A **visszacsapó szelep** (check valve) magától működik: az áramlás egy irányba átengedi, visszafelé zár. Nincs
  rajta kézikerék vagy hajtás, **kezelő nem tudja elzárni**. Ezért leválasztásra nem jó. A benchmark ezért halad át
  rajta, és az első **működtethető szelepnél** (gömbcsap, szelepzár) áll meg.
- **Fontos:** a projekt forrásai a visszacsapó szelep *helyét* igazolják (szivattyú nyomóoldalán, az elzáró és a
  szivattyú között). Azt, hogy *mire való*, egyik elolvasott forrás sem mondja ki szó szerint
  (`pid-szerkezeti-szabalyok.md`, [nem ellenőrzött]). Ezért a „primerbe" csak akkor kerülhet be, ha a kutató talál rá
  idézhető forrást.

## 3. A „primer": egy kis P&ID-mérnöki puska minden modellnek

Ötlet (a tiéd): minden modell kapjon egy rövid, rögzített szöveget alapszabályokkal, mint egy skill-fájl.
Ahhoz, hogy ez **tisztességes** mérés maradjon, ezeket rögzítettük:

- **Minden stratégia ugyanazt a szöveget kapja**, ugyanazon a helyen. Így a stratégiák sorrendjét nem torzítja,
  legfeljebb mindegyiket egyformán emeli.
- **Csak idézhető forrásból készülhet**, soronként hivatkozással. Kérdéssablon, tag vagy válaszformátum nem lehet
  benne.
- **Friss kutató-munkamenet írja**, amely nem látta a hibás válaszokat és a lepecsételt kérdéscsaládokat. Különben a
  primer a teszthez lenne igazítva („tanítás a tesztre").
- **Alapból be van kapcsolva**, és egy kikapcsolt futás méri a hatását (ablációs kísérlet). A szöveget az F1
  befagyasztás rögzíti.

## 4. Az „FV-30-6" csapda

Az ISA-5.1 szerinti műszercímkében a betűk a mért mennyiséget és a funkciót jelölik, a szám a hurok száma. Az
`FIC-30-6` a 30-6-os áramlásszabályozó, az `FT-30-6` az áramlásmérő, az **`FV-30-6` pedig a hurok szelepe**
(végrehajtó elem). A generátorunkban viszont az `FV-30-6` a *beavatkozó* (ActuatingFunction), a szelepháznak saját
neve van (`GV-30-4`). A benchmark ezt várja válaszként. A kérdés („Melyik szelepet működteti a FIC-30-6 hurok?")
tehát kétértelmű: aki ismeri a szabványt, joggal mondja az FV-30-6-ot. Ezért fogalmazzuk át a kérdést (ADR-0040):
„Melyik szelepet mozgatja a hurok beavatkozója? A szelep saját címkéjével válaszolj."

## 5. Gondolkodási erőfeszítés (reasoning effort)

Az olcsó modell (GLM-5.3-flash) „gondolkodó" modell. Válasz előtt rejtett gondolatmenetet ír, amit ugyanúgy
kifizetünk, mint a kimenetet. Az erőfeszítés-paraméterrel (`low`, alapértelmezett, `high`) szabályozható, mennyit
gondolkodjon. Mért eredmény ugyanazon a 36 kérdésen (PAID-02/03):

| Beállítás | Helyes | Költség | Medián idő |
|---|---|---|---|
| alacsony | 27/36 | 0,050 $ | 3,8 s |
| alapértelmezett | 31/36 | 0,0795 $ | 18,5 s |

Az új terv (ADR-0042): a Jev kérdésenként eldönti, hogy elég-e az alacsony erőfeszítés. Az erős modellhez (Sonnet)
csak akkor fordulunk, ha az olcsó modell maga jelzi, hogy elakadt („nincs benne", hibás formátum). Minden beállítás
külön rögzített konfiguráció, ezért az útválasztás utólag, ingyen kiszámítható a már lefuttatott eredményekből.

## 6. Párhuzamos hívások, a sorrend és a költségkorlát megtartásával

Ma a harness egyenként kérdez. A 108 hívásos PAID-02 kb. 50 percig tartott, szinte végig hálózatra várt. A terv
(ADR-0043): egyszerre legfeljebb N kérdés fut (szálakkal). Három dologra kell vigyázni:

- **Sorrend:** a válaszfájlba továbbra is az eredeti sorrendben írunk. Ami előbb elkészül, megvárja az előtte lévőt.
  Így a visszajátszás bájtra azonos marad.
- **Folytatás:** ha a futás megáll, a kész, de még ki nem írt válaszok a gyorsítótárban vannak, és újrainduláskor
  ingyen visszajönnek.
- **Költségkorlát:** a futó kérdések várható költségét előre „lefoglaljuk". Így N párhuzamos kérdés sem csúszhat át a
  beállított dollárhatáron.

Ez a teszteléshez kell. Az, hogy sok felhasználó kérdezi egyszerre ugyanazt a tudásgráfot, külön kérdés: a Neo4j
eleve kiszolgál párhuzamos olvasásokat.
