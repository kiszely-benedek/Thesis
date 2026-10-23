---
topic: Az adapter — miért teszünk egy vékony réteget a pyDEXPI és a saját kódunk közé
status: draft
related: [ADR-0003, pydexpi-szintetikus-generator.md, 40-design/splitter.md]
date: 2026-09-12
---

# Az adapter

## 1. Mi ez, egy hasonlattal

Ha egy magyar hálózati csatlakozós laptopot Angliában akarsz bedugni, nem a laptopot
és nem a fali aljzatot építed át. Veszel egy **átalakítót**, amelynek egyik fele az
angol aljzatba illik, a másik fele a magyar dugót fogadja.

A szoftverben az **adapter** ugyanez: egy kicsi, vékony modul két rész között, amelyek
nem pontosan egyformán "beszélnek". Nálunk az egyik rész a **pyDEXPI** (külső könyvtár,
nem mi írtuk), a másik a **saját kódunk** (a splitter és minden, ami utána jön). Az
adapter az egyetlen hely, amely mindkettőt ismeri.

A projekt ezt már az elején rögzítette: ADR-0003 következményei között szerepel, hogy
a pyDEXPI használatát egy vékony belső adapter modul mögé kell tenni.

## 2. Miért kell nálunk — négy konkrét ok

**1. A két oldal más formában adja és várja a gráfot.** Ezt a forráskódból ellenőriztük:

- A pyDEXPI `GraphLoader`-e `nx.MultiDiGraph`-ot ad vissza. Ebben két csomópont között
  **több párhuzamos él** is lehet.
- A mi splitterünk `nx.DiGraph`-ot vár, ahol két csomópont között **legfeljebb egy él**
  van. Valakinek el kell döntenie, mi legyen a párhuzamos élekkel: összevonjuk,
  megjelöljük, vagy hibát dobunk. Ha ezt senki nem dönti el, a párhuzamos élek
  **csendben elvesznek**.
- A splitter a csomópontokon `node_class` és `tag` attribútumot keres, és a
  berendezés-kategóriák alapból `vessel`, `pump`, `exchanger`, `column`, `tank`
  (`SplitConfig`). A pyDEXPI viszont DEXPI osztálynevekkel dolgozik. A kettő közötti
  fordítás (melyik DEXPI osztály számít szivattyúnak) is az adapter dolga.

**2. Reprodukálhatóság.** A pyDEXPI generátora a globális `random` modult használja, és
nincs seed paramétere (lásd `pydexpi-szintetikus-generator.md`, 5. szakasz). A mi
szabályunk viszont: ugyanaz a seed mindig ugyanazt a benchmarkot adja. Az adapter tudja
ezt áthidalni: beállítja a seedet, generál, majd visszaállítja a korábbi állapotot.

**3. Egyetlen helyen függünk tőle.** Ha a pyDEXPI egy új verzióban átnevez egy
függvényt, csak az adapter egy fájlját kell javítani, nem a fél projektet. A splitter
tesztjei ma is pyDEXPI nélkül futnak, és ennek így is kell maradnia: a tesztek gyorsak
és függetlenek maradnak.

**4. Cserélhetőség.** Ha egyszer mégis más generátort akarunk (akár egy saját, egyszerűt),
csak az adaptert kell kicserélni. A licencproblémát az ADR-0003 lezárta, de a
cserélhetőség ettől függetlenül hasznos.

## 3. Mikor nem kell

Ha a generálásra **nem a pyDEXPI-t**, hanem egy saját, egyszerű generátort használunk,
akkor generáláshoz nem kell pyDEXPI-adapter. Beolvasáshoz viszont később valószínűleg
igen: a ChatP&ID baseline (EXP-0001) egy valódi DEXPI XML fájlon fut (`DEXPIEX01.xml`),
és azt a pyDEXPI olvassa be. Hogy melyik generátor legyen, azt a most futó tervezési
feladat dönti el.

## 4. Tévhitek

**"Az adapter felesleges réteg, közvetlenül is hívhatnánk a pyDEXPI-t."** Hívhatnánk,
de akkor a párhuzamos élek kezelése, az osztálynevek fordítása és a seed kezelése
szétszóródna a kódban, és mindenhol kicsit másképp történne.

**"Az adapter minden pyDEXPI-függvényt becsomagol."** Nem. Csak azt a néhány dolgot
teszi elérhetővé, amire nekünk szükségünk van, a mi formánkban. Vékony, ezért könnyű
átlátni és tesztelni.

**"Ha van adapter, a pyDEXPI hibái nem érintenek."** De érintenek. Az adapter nem javítja
a könyvtár hibáit, csak egy helyre gyűjti, hol találkozunk velük.
