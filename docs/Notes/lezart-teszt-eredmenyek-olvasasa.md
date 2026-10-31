---
topic: Lezárt teszteredmények olvasása — intervallumok, előre rögzített állítások, általánosítási rés
status: draft
related: [ADR-0053, ADR-0060, ADR-0061, ADR-0062, kaszkad-onjelzes.md, vedes-02-hatter.md]
---

# Lezárt teszteredmények olvasása

Forrás: az EXP-0007 R5 futás jelentése, `data/runs/exp0007/sealed/report/report.md`. A futás 2026-10-31-én
készült. Minden szám innen származik, kivéve azt a hármat, amelyet a 3. részben magunk számolunk újra
ellenőrzésképpen.

## 1. Miért kell ez egyáltalán

Az 1 000 lapos korpuszon a fő rendszer (`cascade_v4_iso`) 440 kérdésből 392-t válaszolt meg helyesen, ez 0,891. A
100 lapos korpuszon 401/440, ez 0,911. Felmerül a kérdés: romlott-e a rendszer a tízszer nagyobb üzemen?

Puszta szemmel nem lehet eldönteni. Ha ugyanazt a rendszert egy másik 440 kérdéses húzáson futtatnánk, az eredmény
véletlenül is elmozdulna pár százalékpontot. Ezért három dologra van szükség:

1. **Bizonytalansági sávra** minden szám körül, hogy lássuk, mekkora a mérési zaj.
2. **Előre rögzített állításokra**, vagyis a futás előtt leírt kérdésekre és küszöbökre (ADR-0053). Ha a mérés után
   választanánk küszöböt, mindig azt találnánk meg, amelyik a nekünk kedvező eredményt adja.
3. **Kérdésfelosztásra.** Külön kell mérni azokon a kérdéstípusokon, amelyeken hangoltunk, és azokon, amelyeket
   a hangolás során soha nem láttunk.

## 2. A fő gondolat

### 2.1. Wilson-intervallum: sáv egy arány körül

Ha *n* kérdésből *k* a helyes válasz, a pontosság p = k/n. A 95%-os Wilson-intervallum azt a sávot adja meg,
amelyben a „valódi” pontosság a mintánk alapján hihetően lehet. A tankönyvi „p ± 1,96·√(p(1−p)/n)” képlet 1 közelében
és kis *n* mellett rossz eredményt ad, például 1-nél nagyobb felső határt. A Wilson-képlet ezt kijavítja, ezért
pontossághoz ezt használjuk.

**Ökölszabály:** a sáv szélessége nagyjából 1/√n-nel arányos. 440 kérdésnél ±3 pont körül van, 100 kérdésnél
±8 pont körül. Emiatt bizonytalanabbak a held-out (100 kérdés) számai, mint a fő számok (440 kérdés).

### 2.2. Párosított bootstrap: két rendszer különbsége ugyanazokon a kérdéseken

Ha két rendszert *ugyanazon* a 440 kérdésen futtatunk, a kérdések nehézsége közös zaj. A párosított összehasonlítás
ezt a közös zajt kiszűri. Az eljárás:

1. Visszatevéssel húzunk 440 kérdést az eredeti 440-ből.
2. Ezen a húzáson kiszámoljuk az A pontossága mínusz a B pontossága különbséget.
3. Ezt tízezerszer megismételjük, és a különbségek 2,5. és 97,5. percentilise adja a 95%-os intervallumot.

Ugyanezt csináljuk költségre és válaszidőre is. Így „nem párosított” (*unpaired*) intervallum csak ott marad, ahol
a két minta tényleg különböző kérdésekből áll: a 100 lapos és az 1 000 lapos korpusz kérdései mások.

### 2.3. Költség-elaszticitás: mennyire nő a költség a lapszámmal

e = ln(költségarány) / ln(laparány). Ha e = 1, a költség egyenesen arányos a lapszámmal. Ilyen az a módszer, amely
az egész rajzanyagot bemásolja a promptba (ContextRAG). Ha e = 0, a költség nem függ a lapszámtól.

### 2.4. A felosztás

| Felosztás | Kérdés / korpusz | Mit jelent |
|---|---|---|
| dev-old | 220 | A hangolás alatt is használt 18 kérdéstípus, a régi mintavétellel |
| dev-new | 120 | Ugyanaz a 18 típus, új húzással |
| **held-out** | **100** | 5 kérdéstípus, amelyet a hangolás során soha nem húztunk |
| held-out-wording | 90 | Fejlesztési kérdések más megfogalmazásban |
| **headline** | **440** | dev-old + dev-new + held-out, tehát **a held-out is benne van** |

Ez kiadja a 440 + 90 = 530 kérdést. A korpuszonkénti 560 kérdésből a maradék 30 a `LOOP_ACTUATED_VALVE`
típusé, amelyet a headline nem számol (ADR-0044 U2).

## 3. Kidolgozott példa: az 1 000 lapos korpusz

A három újraszámolt érték ezzel a Pythonnal ellenőrizhető, és mind egyezik a jelentéssel:

```python
import math

def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(centre - half, 3), round(centre + half, 3)

print(wilson(392, 440))  # (0.858, 0.917)  fő rendszer, 1 000 lap
print(wilson(74, 100))   # (0.646, 0.816)  ugyanaz, csak held-out
print(round(math.log(0.00148 / 0.00137) / math.log(10), 3))  # 0.034, a jelentés 0.033-at ír (kerekítés)
```

**Az állítások egyenként, az 1 000 lapos korpuszon (headline):**

| Állítás | Mit kérdez | Mért érték | Eredmény |
|---|---|---|---|
| **Q4 (fő)** | Nem romlik-e a pontosság 100 → 1 000 lapnál, és nem nő-e meredeken a költség? | −0,020 [−0,059; +0,018]; e = 0,033 | **TELJESÜL** |
| K1 | A kaszkád pontosabb, olcsóbb *és* gyorsabb-e, mint ha mindig az ágens válaszolna? | pontosság +0,020 (rendben), költség −0,00041 $ (rendben), idő **+3,21 s** | **NEM** |
| K2 | Jól dönt-e az önjelzés arról, hogy mikor kell továbbadni a kérdést, vagy egy véletlen továbbadás is ugyanilyen jó lenne? | +0,076 [+0,055; +0,098] | TELJESÜL |
| K3 | Elég gyors-e (medián ≤ 10 s, p90 ≤ 60 s)? | 7,5 s és 40,8 s | TELJESÜL |
| Q5 | A típusos eszközöket használó ágens jobb-e a szabad Cypher-nél? | +0,075 [+0,039; +0,111] | TELJESÜL |

**Hogyan olvassuk a Q4-et?** A különbség intervalluma tartalmazza a nullát, és az alsó határa −0,059. Ebből
**nem** az következik, hogy a pontosság biztosan nem romlik. Annyi következik, hogy a mérés nem talált romlást,
és ha van romlás, az legfeljebb kb. 6 pont. Az eredményt mindig ezzel a pontos megfogalmazással kell közölni.

**Miért bukik a K1, és miért nem baj?** A kaszkád először a Cypher-szinttel próbálkozik, és csak ha az nem elég
biztos, adja tovább a kérdést az ágensnek. A továbbadott kérdéseken így két lépés ideje adódik össze. Emiatt lassabb,
mint ha mindig közvetlenül az ágens válaszolna. Cserébe olcsóbb, és nem pontatlanabb. A konzulens szerint a
pontosság a cél, nem a gyorsaság, és a K3 időkorlátját a kaszkád így is teljesíti.

**Általánosítási rés.** Az 1 000 lapos korpuszon a fejlesztési kérdéseken a pontosság 318/340 = 0,935, a held-out
kérdéseken 74/100 = 0,740. A rés +0,195, intervalluma [+0,108; +0,288]. Érdemes megnézni, hol keletkezik:

| Held-out kérdéstípus | 100 lap | 1 000 lap |
|---|---|---|
| `DOWNSTREAM_ISOLATION` (mely szelepeket kell elzárni lefelé) | 2/20 | 2/20 |
| `VALVES_ON_PATH` | 15/20 | 13/20 |
| `FEEDING_UNITS` | 20/20 | 20/20 |
| `UNITS_REACHED` | 20/20 | 20/20 |
| `ROUTE_AVOIDING` | 20/20 | 19/20 |

A rés szinte teljes egészében **egyetlen kérdéstípusból** jön. A `DOWNSTREAM_ISOLATION` nélkül a held-out eredmény
72/80 = 0,90. A fejlesztési típusok közül a rokon `UPSTREAM_ISOLATION` is gyenge: 16/30 az 1 000 lapos korpuszon.
**Az olvasatom ebből** (ez értelmezés, nem mért állítás): a rendszernek nem általában a hangolás általánosításával
van gondja, hanem az *elzárási* kérdésekkel. Ezekben azt kell eldönteni, mely szelepek zárásával lehet egy
berendezést leválasztani. A jelentés egy másodlagos pontozást is tartalmaz arra az esetre, ha a szabályozószelepek
nem számítanak elzárónak. Eszerint maga az aranykulcs (a helyes válaszok) definíciója is vitatható.

## 4. Hol használjuk

- **ADR-0053:** az állítások és a küszöbök a v1 lezárt tesztjénél rögzültek. Az ADR-0060/0061 változatlanul viszi
  át őket a v2-re, a V2T rendszerre.
- **ADR-0062:** az R5 eltérései. Kimaradt a `FIRST_MEETING_POINT` típus, megemeltük a költségkorlátokat, és egy
  visszajátszás időzítés miatt leállt.
- A held-out típusokat szándékosan nem húztuk ki az R5 előtt. Ez a biztosíték a túlhangolás ellen.

## 5. Gyakori félreértések

1. **„Átfedő intervallumok = nincs különbség.”** Párosított mérésnél ez nem igaz. A kaszkád és a csak-ágens
   pontosságának intervalluma átfed, a K2 párosított különbsége mégis egyértelműen pozitív. A különbség
   intervallumát kell nézni, nem a két külön intervallumot.
2. **„A Q4 TELJESÜL azt jelenti, hogy nincs romlás.”** Nem. Azt jelenti, hogy a mérés nem talált romlást, és a
   lehetséges romlás felső becslése kb. 6 pont.
3. **„95% a valószínűsége, hogy a valódi érték a sávban van.”** Pontosan: az eljárás az esetek 95%-ában fogja be a
   valódi értéket. Egy konkrét sávra vonatkozó valószínűségi kijelentés Bayes-i keretet igényelne.
4. **„A headline szám a hangolt kérdéseken mért pontosság.”** Nem: a headline a held-out típusokat is tartalmazza.
   Ezt én magam is elrontottam a chatben 10-31-én, és utána kijavítottam.
5. **„Sok állítás → valamelyik véletlenül teljesül.”** Ez valós veszély, ezért egyetlen fő állítás van (Q4), és
   minden küszöb a futás előtt rögzült.

## 6. Ha csak egy dolgot olvasol

[Binomial proportion confidence interval — Wilson score interval (Wikipedia)](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval)
