# Fejlesztői és tesztadat — miért nem próbálgatunk a tesztüzemen

*Tanító jegyzet, 2026-10-04. A kérdés: „miért szabálytalan, hogy a H100-on futtattuk, az a tesztüzem?”*

## Az alapgondolat egy hasonlattal

Ha egy diák a vizsga előtt megkapja a vizsgafeladatokat, gyakorol rajtuk, és a vizsgán 95 %-ot ír, a 95 % nem
azt méri, mennyire tud, hanem azt, mennyire emlékszik ezekre a feladatokra. A jegy **optimista**, és senki nem
tudja megmondani, mennyire.

Gépi tanulásban és mérésben ugyanez a szabály: az adatot szét kell választani.

| Halmaz | Mire való | Szabad-e ránézni a hibákra? |
|---|---|---|
| **fejlesztői** (dev) | hangolás, hibakeresés, ötletek kipróbálása | igen, ez a dolga |
| **teszt** | a végső szám, amit a dolgozat közöl | **nem** — csak egyszer, a rendszer befagyasztása után |

Ha a teszthalmaz hibáit nézve javítunk a rendszeren, a rendszer *hozzáidomul* a teszthalmazhoz. Ezt hívják
**szivárgásnak** (leakage) vagy a teszthalmaz „elhasználásának”: a teszt már nem független próba.

## Nálunk

- **D100, D1000** — fejlesztői üzemek. Ezeken szabad bármit kipróbálni.
- **H100, H1000** — tesztüzemek, a dolgozat főtáblázata (ADR-0015). A rendszert előbb befagyasztjuk (F1, a
  fájlok lenyomatát rögzítjük), utána fut rajtuk a végső mérés.
- **Lezárt (held-out) kérdéscsaládok** (ADR-0035) — hat olyan kérdéstípus, amelynek a leírása egy lepecsételt
  fájlban van (sha256 rögzítve 2026-10-02). Csak a befagyasztás után nyitjuk ki, és csak a tesztüzemeken
  generálunk belőlük kérdést. A fő állítás (Q3) a H1000-en, ezeken a családokon dől el.

## Mi történt

A PAID-01…04 és a PG-P1 fizetős próbák a **H100-on** futottak, fejlesztői kérdéscsaládokkal, egy 36 kérdéses
szeleten. A hibáikat megnéztük (pl. T-11-1, P-3-1, a szabályozókör-szelep kérdés), és ezek alapján változtattunk:
üzemgráf-ábrázolás, fejlécek, primer. Ez a sorrend fordított: a hibakeresésnek fejlesztői üzemen lett volna a helye.
Utólag a tervdokumentum (F11 sor) rögzítette: ezek a számok nem kerülnek a dolgozatba, a további próbák fejlesztői
üzemen mennek.

## Mennyire nagy a baj

Korlátozott, mert:

1. A változtatások **általánosak** (formátum, magyarázat, forrásokból vett szakmai tudás), nem a H100-ra hangolt
   számértékek.
2. A **H1000-at** fizetős próba nem érintette.
3. A **lezárt családokat** senki nem látta — a fő állítás azokon dől el.
4. A H100-on látott 36 kérdés számait nem közöljük.

De nem nulla: a H100 végső eredménye kissé optimista lehet a fejlesztői családokon. Ezt a dolgozat korlátai között
őszintén ki kell mondani — vagy a H100-at új seeddel újra kell generálni, mielőtt bármi végső fut rajta, mert
az üzemek seedből készülnek, így egy új seed egy soha nem látott üzemet ad.
