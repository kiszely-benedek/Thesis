---
topic: OPEN100 csatlakozó-megoldókulcs — párba állított, lógó, megoldatlan
status: draft
related: [ADR-0005, 40-design/open100-annotation.md, pid-lapkozi-csatlakozok.md, models.py]
---

# Az OPEN100 csatlakozó-megoldókulcsa: párba állított, lógó, megoldatlan

## Miért van ez

Egy zászló elolvasása (lásd `pid-lapkozi-csatlakozok.md`) megmondja, mit *mond* az a zászló. Egy benchmarknak több kell: minden zászlóhoz egy eldöntött állítás arról, mi a helyes válasz, ha a rendszert megkérdezik: "hol folytatódik ez a cső?" Néha a válasz egy másik zászló. Néha az, hogy "egy rajzon, ami nincs a birtokunkban". Néha maga a rajz teszi lehetetlenné a választ. Mindhárom jogos válasz, és egy megoldókulcs, amelyik csak az elsőt rögzíti, a tippelést jutalmazná.

Ezért a 96 OPEN100 csatlakozó mindegyike pontosan egy vödörbe kerül a háromból, és egy ellenőrzés (`SplitManifest.accounted_for()`) nem engedi kiírni a megoldókulcsot, ha bármelyik csatlakozó mindhárom vödörből kimaradt.

## Az alapgondolat

**Párba állított (paired).** Két zászló ugyanannak a csőnek a két vége. `ConnectorPair`-ként rögzítjük, egy `match_rule` mezővel, ami megmondja, mennyire biztos a pár — a legerősebbtől a leggyengébbig:

| Szabály | Bizonyíték | Mit jelent a mérésben |
|---|---|---|
| `line_number` | ugyanaz a vezetékszám van mindkét csövön, és mindkét zászló a másik lapját nevezi meg | arany: ezt egy rendszernek meg kell találnia |
| `grid_mutual` | nincs közös vezetékszám, de a két zászló egymás lapjára mutat, és nincs más jelölt | szilárd, de azon áll, hogy a rajzok teljesek |
| `service_direction` | csak a rendszerkód és az áramlási irány illik, kizárásos alapon | leggyengébb: benne marad a kulcsban, de külön jelentjük, hogy ne dobja fel a pontszámot |

A szabályt páronként pont azért rögzítjük, hogy egy eredményt úgy lehessen idézni: "pontosság a 19 vezetékszámos páron", és a két gyenge ne mossa össze.

**Lógó (dangling).** A zászló olyan rajzra hivatkozik, amelyik nincs a tizenkettő között. Az OPEN100 a 130, 190, 240, 250, 270, 290, 300 és 320 rajzokra hivatkozik, és ezek egyike sincs a PID2Graph-ban. Ez a 42 zászló nem hiba. Ez a tartózkodás (abstention) természetes tesztje: a jó válasz az, hogy "az a rajz nincs a korpuszban", és aki párt talál ki hozzá, téved.

**Megoldatlan (unresolved).** A célrajz *megvan*, vagy a zászló egyáltalán nem ad rajzszámot, és mégsem felel meg egyetlen jelölt sem a próbáknak. Nyolc maradt, mindegyiknek leírt indoka van. Felismerhető fajtákba esnek — mind olyan, ami egy valódi üzem rajzaiban is elő fog fordulni:

- **Kétszer megrajzolt.** Az 1/5 egy "DETAIL A" dobozban van, amely ugyanazt a szelepet és műszereket rajzolja újra, mint az 1/73 a fő nézetben. Egy kapcsolat, két kép.
- **Duplikált vezetékszám.** A 4. lapon két zászló is `165117`-es a kondenzátum lapról, ahol csak egy ilyen zászló van. Az egyiknek (4/117) nem lehet párja.
- **Elírt hivatkozás.** A 7/34 azt mondja: "pótvíz a 160-as rajzról"; a 160-as rajzon nincs ilyen zászló, és minden más pótvíz-zászló a 200-as rajzra hivatkozik.
- **Egyirányú hivatkozás.** A 9. lap kétszer mutat a 11. lapra (9/2, 9/59); a 11. lap egyszer sem mutat vissza.
- **Nincs rajzszám.** A 11/22 csak ennyit mond: `REACTOR WATER SERVICE TANK`. Ilyen nevű tartály a 12 lap egyik berendezés-jegyzékében sem szerepel.
- **Nem is csatlakozó.** A 7/35 egy 17×8 képpontos karimajel, amit a PID2Graph tévesen csatlakozónak címkézett.

A "megoldatlan" nem a "még nem néztük meg" vödre. Ítélet, indokkal.

## Kidolgozott példa: párosítás kizárással

7. lap, 7/33 zászló: `ACW PID 210-2 (F-1)`, nyíl a lap belseje felé. Bejövő a 210-es rajz 2. lapjáról — ez a 8. lap —, és a párnak az F sor jobb szélén kellene ülnie.

8. lap, F sor, jobb szél: a 8/5 zászló felirata `SWS PID 130-1`. Azt állítja, az üzemivíz-rajzra megy, nem a 7. lapra. A rácsmező rossz zászlóhoz vezetett. Ugyanennek az egyenes fejvezetéknek a másik végén, bal szél, F sor, ott a 8/54: `ACW PID 210-1`, nyíl kifelé. Ez az egyetlen kimenő zászló a 210-es rajz 1. lapjára a 8. lapon, és a 7/33 az egyetlen párosítatlan bejövő a 8. lapról a 7. lapon.

Vezetékszámok: a 7/33-on `FWS-175271`; a 8/54 fejvezetékén `111156`. Nem egyezik. Az 1. szabály elbukik, a 2. is, mert a rácsmező ellentmond, a 3. kizárással teljesül. `service_direction`-ként rögzítve, az ellentmondás a megjegyzésben. Ez az őszinte válasz: valószínűleg egy cső, gyenge bizonyítékkal, egy önmagának ellentmondó rajzban.

## Hová illik

A három vödör az, amihez a kísérletek mérnek. A lapközi összekapcsolás (EXP-0004) precizitást és fedést mér a párokon, szabályonként bontva. A tartózkodás (EXP-0005) azt méri, mondja-e a rendszer, hogy "nincs a korpuszban", a 42 lógó zászlón. A nyolc megoldatlan mindkét pontszámból kimarad, de a manifestben megmarad, mert az a rendszer, amelyik a 4/117-re azt jelenti, hogy "ennek nincs következetes párja", *helyesen* jár el, és ezt látni akarjuk. Ugyanezt a `SplitManifest` alakot adja majd a szintetikus splitter is (`splitter.md`), így a későbbi kód nem tudja, melyik forrást olvassa.

## Tipikus félreértések

- **"A megoldatlan azt jelenti, nem sikerült elolvasni."** Nem. Mind a nyolcat legalább kétszer olvastuk el a forráslapból vágott széles kivágásról. Megoldatlan = a rajz nem enged meg párt.
- **"A gyenge párt el kellene dobni."** Nem. Ha eldobnánk, a megoldókulcs azt állítaná, hogy a cső nem folytatódik — ez nagyobb tévedés, mint egy megjelölt gyenge kapcsolat. Megtartani, megjelölni, külön jelenteni.
- **"A lógó zászlók zaj, ki kell szűrni."** Az adathalmaz értékének a fele. Senki másnak nincs valódi, természetesen előforduló "a válasz nincs itt" esete P&ID-kre.
- **"A darabszámok az eredmény."** 23 pár, 42 lógó, 8 megoldatlan: ez tizenkét rajz leírása, nem eredmény. Az eredmény az lesz, hogyan teljesít ellenük egy visszakereső rendszer.

## Ha egy dolgot olvasol el

`docs/private/40-design/open100-annotation.md`, a "Third read" szakasztól: a konkrét szabályok, amelyek minden vödör-besorolást előállítottak, a rajzhibák egyenként felsorolva.
