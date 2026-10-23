---
topic: AGPL-3.0 — mit jelent a copyleft a saját repódra, és miért ránt magával a pyDEXPI
status: draft
related: [ADR-0003, lpg-vs-rdf.md]
date: 2026-09-06
---

# AGPL-3.0 — mit vállaltál azzal, hogy a repó gyökerébe került egy `LICENSE` fájl

2026-09-06-án a repó AGPL-3.0 licencet kapott (ADR-0003, ideiglenesen alkalmazva). Ez a jegyzet
azt magyarázza el, miért nem volt ez szabad választás, mit jelent a gyakorlatban, és mi az a két
kérdés, amit a professzornak fel kell tenned.

## Miért létezik egyáltalán a copyleft?

A szabad szoftveres licencek két nagy családra oszlanak, és a különbség egyetlen kérdés: **mi
történik, ha valaki továbbadja a kódot?**

- A **megengedő** (permissive) licencek — MIT, BSD, Apache-2.0 — azt mondják: csinálj vele, amit
  akarsz, csak a szerző nevét hagyd rajta. Egy MIT-licencű könyvtárat beépíthetsz zárt, kereskedelmi
  termékbe is.
- A **copyleft** licencek — GPL, LGPL, AGPL — azt mondják: használhatod, módosíthatod, terjesztheted,
  **de amit belőle építesz és továbbadsz, azt ugyanezzel a szabadsággal kell továbbadnod.** A szabadság
  "ragad": ez a copyleft. A célja az, hogy a szabad kód szabad is maradjon, ne lehessen zárt
  termékbe elnyelni.

A GPL-családon belül az **AGPL** (Affero GPL) egy fokkal szigorúbb, és ezt a fokot érdemes érteni.

## Az alapgondolat: a "terjesztés" váltja ki a kötelezettséget

A GPL-nél a kötelezettség akkor áll be, ha a programot **terjeszted** — azaz odaadod valakinek a
bináris vagy forrás formában. Aki csak a saját gépén futtat GPL-es kódot, és senkinek nem adja
tovább, arra nincs kötelezettség.

A 2000-es évek webes világában ez kiskaput nyitott: egy cég fogott egy GPL-es kódot, ráépített egy
webszolgáltatást, és a *felhasználók a hálózaton keresztül használták*, de a program soha nem
"terjesztődött" — tehát nem kellett kiadni a forrást. Az AGPL ezt zárja be: **ha a programot hálózaton
keresztül teszed elérhetővé másoknak, az is terjesztésnek számít**, és a felhasználóknak jár a forrás.

Rád vetítve: ha a dolgozat chatbotját egyszer weben demózod (a professzornak, egy konferencián,
bárkinek), az AGPL alatt már kötelezettség, hogy a futó verzió forrása elérhető legyen. Mivel a repó
nyilvános a GitHubon, ez a gyakorlatban teljesül — de tudni kell róla.

## Miért nem volt választás: a "derivative work" fogalma

Itt van a pont, amit a legtöbben elhibáznak, és amit az ADR-0003 külön hangsúlyoz.

A **pyDEXPI** (a DEXPI adatmodell Pydantic-osztályai, Proteus XML betöltés, szintetikus P&ID
generálás) AGPL-3.0 licencű. Ha a `plantgraph` csomag `import pydexpi`-t ír, akkor a jogi értelmezés
szerint a `plantgraph` a pyDEXPI **származékos műve** (derivative work). Ez akkor is így van, ha egy
sort sem módosítasz a pyDEXPI-ben, és akkor is, ha csak "használod" — a GPL-család szerint a
könyvtár *összekapcsolása* a programoddal már származékos művet hoz létre.

A következmény: ha a repó nyilvános (és az), és importálja a pyDEXPI-t (fogja), akkor **a repó licence
csak AGPL-3.0-kompatibilis lehet**. Egy MIT-licencű `plantgraph`, ami pyDEXPI-t importál,
licencsértés lenne — nem a te részedről közvetlenül, hanem a kombináció terjesztése révén.

Ezért lett a döntés az ADR-0003 **A opciója**: elfogadjuk az AGPL-t. A **B** (újraírni a szükséges
DEXPI-részhalmazt) hetek munkája egy megoldott problémán; a **C** (a pyDEXPI-t külön folyamatba
zárni, fájlokon át kommunikálni) jogilag vitatott, egy dolgozat nem építhet rá.

## Egy kidolgozott példa: mi változik a mindennapokban?

Semmi olyan, ami a kutatást akadályozná. Konkrétan:

| Tevékenység | AGPL alatt |
|---|---|
| Fejlesztesz, commitolsz, pusholsz a nyilvános repóba | Semmi extra — a forrás elérhető, ez maga a teljesítés |
| Beadod a dolgozatot a kóddal | Rendben; a `LICENSE` fájl a repóban van |
| Weben demózod a chatbotot | A futó verzió forrása legyen elérhető — a nyilvános GitHub ezt teljesíti, ha a demó a pusholt kóddal fut |
| Valaki forkolja és tovább fejleszti | Ő is AGPL alatt kell, hogy közzétegye — ez a copyleft lényege |
| A professzor ipari partnere zárt termékbe akarja tenni | **Nem lehet** relicencelés nélkül — ez az ADR-0003 2. nyitott kérdése |

Ami a repóban történt 2026-09-06-án:

```
LICENSE              ← az AGPL-3.0 teljes szövege a gnu.org-ról, változatlanul
pyproject.toml       ← license = { text = "AGPL-3.0-only" }
README.md            ← "Licence" szakasz átírva
```

Az `AGPL-3.0-only` egy **SPDX-azonosító**: gépileg olvasható, egyértelmű licencnév. Az `-only` azt
jelenti, hogy pontosan a 3.0-s verzió alatt adod ki (nem "3.0 vagy későbbi"). Ezt választottuk, mert
így a pyDEXPI-vel azonos a licenc, nincs kompatibilitási kérdés.

## Hová illik a dolgozatban?

Az ADR-0003 státusza **továbbra is `proposed`**, mert két kérdés nyitott, és azokat csak a professzor
tudja megválaszolni. Addig a licenc *ideiglenesen* van alkalmazva, és a csomag még nem importálja a
pyDEXPI-t, tehát semmi nem visszafordíthatatlan. A két kérdés:

1. **Van-e az egyetemnek szellemi tulajdonra vonatkozó szabályzata a szakdolgozati kódra?** Egyes
   egyetemek az intézményt teszik a hallgatói munka jogtulajdonosává, vagy előírják a licencet. Ha
   van ilyen, az felülírja a te választásodat.
2. **Vár-e bárki (ipari partner, tanszéki projekt) zárt, tulajdonosi felhasználást a kódból?** Ha
   igen, az AGPL akadály, és vissza kell menni az ADR-0003 B vagy C opciójához, *mielőtt* az első
   pyDEXPI-import bekerül.

Ha bármelyikre "igen, probléma" a válasz, új ADR írja felül az ADR-0003-at.

## Gyakori félreértések

1. **"Csak használom a könyvtárat, nem módosítom, tehát nem érint."** — A GPL-család szerint az
   összekapcsolás is származékos művet hoz létre. Ez a leggyakoribb tévedés.
2. **"Az AGPL megtiltja a kereskedelmi használatot."** — Nem. Kereskedelmi célra is használható; azt
   írja elő, hogy a forrást a felhasználók megkapják. A pyDEXPI README-je ezen felül *külön* azt is
   mondja, hogy kereskedelmi/tulajdonosi használathoz keresd a fejlesztőket alternatív licencért —
   ez a *pyDEXPI szerzőinek* saját kikötése, nem az AGPL-é.
3. **"Ha a repó privát, nincs kötelezettség."** — Privát repó + saját gépen futtatás esetén valóban
   nincs terjesztés. De a te repód nyilvános, a dolgozatot be kell adni, és a chatbotot demózni
   fogod — mindhárom terjesztés.
4. **"A LICENSE fájl bemásolása elég."** — A fájl a minimum. Ezen felül a README-ben ki kell mondani
   (megtörtént), és illik minden forrásfájl fejlécében is jelezni; ez utóbbi ajánlás, nem előírás, és
   ebben a repóban még nem tettük meg.
5. **"A dolgozat szövege is AGPL lesz."** — Nem. A licenc a *szoftverre* vonatkozik. A dolgozat szövege,
   a jegyzetek, az ábrák külön szerzői jogi kérdés; ezekre az egyetem beadási szabályai vonatkoznak.

## Ha egy dolgot olvasol el

A Free Software Foundation "Why the Affero GPL" oldala — három bekezdés, pontosan a hálózati
kiskapuról és arról, miért zárták be: <https://www.gnu.org/licenses/why-affero-gpl.html>
