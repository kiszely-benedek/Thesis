# Kaszkád, önjelzés, és hogyan válasszunk szabályt túlillesztés nélkül

*Tanulási jegyzet, 2026-10-04. Háttér: ADR-0046 és a `40-design/method-and-effort-cascade.md` terv.*

## 1. Mi az a kaszkád?

Kaszkádnak (lépcsőnek) azt hívjuk, amikor egy kérdést **először a legolcsóbb módszer** kap meg, és csak akkor
megy tovább egy drágább lépcsőre, ha az olcsó válasz **gyanús**. Nálunk:

1. **1. lépcső – CypherRAG, GLM, alacsony erőfeszítés.** A modell ír egy Cypher-lekérdezést, a Neo4j lefuttatja,
   a modell a találatokból válaszol. Kérdésenként kb. $0.00023, medián 1,5 s (D100).
2. **2. lépcső – kérdésfüggő Hierarchical az üzemgráfon, GLM, alapértelmezett erőfeszítés.** A teljes kiválasztott
   gráfrészletet kapja meg. Kb. $0.0026 kérdésenként, medián 7,8 s.
3. **3. lépcső – ugyanez egy másik konfigurációval** (mimo-modell vagy GLM alacsony erőfeszítéssel), csak akkor, ha
   a 2. lépcső „elszállt".

## 2. Mi az önjelzés (self-flag)?

Olyan jel, amit a lépcső **saját maga** ad arról, hogy valószínűleg rossz a válasza — és amihez **nem kell tudni a
helyes választ**. Példák:

- a Cypher-lekérdezés hibát dobott, vagy **üres eredményt** adott;
- a modell azt felelte, hogy „nincs ilyen az adatokban" (`not_present`);
- **elszállás** (runaway): a gondolkodó modell elhasználta mind a 16 384 kimeneti tokent, és nem adott választ.

A D100-on a Cypher 180 válaszából 125 „tiszta" (nincs hiba, van találat, nem tagad), ezekből 118 helyes. A maradék
55-ből csak 23 helyes — tehát a jel valóban elválasztja a jó és a rossz válaszokat.

**Arany adat (gold)** az, amit csak a pontozó tud: a helyes válasz, a kérdéscsalád, a `k` távolság. Ha egy útválasztó
ezeket olvasná, az csalás lenne (ezt hívjuk **orákulumnak**; csak felső korlátként jelentjük).

## 3. Miért nem címke szerint választunk módszert?

A szabályalapú osztályozó minden kérdéshez ad egy „információigény-címkét" (pl. PATH, SIGNAL_CHAIN). Csábító lenne
azt mondani: „PATH-kérdést a Cypher kapja, SIGNAL_CHAIN-t a Hierarchical". A D100-on ez 167/180-at adna — de ezt a
9 döntést **ugyanazon a 180 kérdésen** hoztuk meg, amin mérjük. Ez a **túlillesztés** (overfitting): a szabály a
mért adatot tanulja meg, nem az általános összefüggést. A rejtett (sealed) kérdéscsaládoknál senki sem tudja, melyik
módszer jobb az ő címkéjükre.

Az önjelzéses kaszkád **egyetlen paramétert sem** illeszt az adatra („csak nem üres, nem tagadó választ fogadunk el"),
mégis 167/180-at ér el a D100-on, feleannyi költséggel, mint a mindig-Hierarchical (157/180).

## 4. Fejlesztői és tesztkorpusz – a választás sorrendje

1. **Most** leírjuk a jelölteket és a kiválasztási szabályokat (S1–S3), még mielőtt új fizetős futás lenne.
2. **D100** (fejlesztői): itt nézzük meg a jeleket és választunk.
3. **D1000** (második fejlesztői korpusz, 10× nagyobb üzem): itt **ellenőrizzük**, hogy a választás megáll-e — itt a
   jeleket senki sem nézte előre. Ez a *méret* próbája, nem az új kérdéstípusoké.
4. **Fagyasztás (F1)**: a szabály fájljait hash-sel rögzítjük.
5. **Teszt** (H100, H1000, rejtett családokkal): csak ekkor nyitjuk ki a lepecsételt kérdéscsaládokat.

## 5. Két összehasonlítási alap

- **Véletlen eszkaláció:** ugyanannyi (55) kérdést véletlenszerűen küldünk tovább. Ha az önjelzés nem jobb ennél,
  akkor a jel semmit sem ér. D100-on a véletlen átlag 145,8, a kaszkád 167.
- **Páros bootstrap-konfidenciaintervallum:** sokszor újramintavételezzük ugyanazt a 180 kérdést, és megnézzük, a
  különbség (kaszkád − mindig-Hierarchical) mennyire ingadozik. Ha a 95 %-os intervallum nem tartalmazza a 0-t, a
  különbség valószínűleg nem a véletlen műve. D100-on: pontosság +0,056 [+0,006; +0,106] — de ez fejlesztői adat,
  a dolgozatban csak a tesztfutás számai szerepelhetnek bizonyítékként.
