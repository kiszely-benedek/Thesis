---
topic: ADR-ek életciklusa — mit jelent a proposed és az accepted, és miért nem írjuk át az elfogadott döntéseket
status: draft
related: [ADR-0004, ADR-0006, ADR-0007, 20-decisions/_TEMPLATE.md]
date: 2026-09-12
---

# ADR-ek életciklusa

## 1. Mi az ADR

Az **ADR** (Architecture Decision Record, magyarul nagyjából "tervezési döntési
jegyzőkönyv") egy rövid dokumentum egyetlen döntésről. Leírja:

- mi volt a helyzet (**Context**),
- milyen lehetőségek voltak (**Options considered**),
- mit döntöttünk (**Decision**),
- miért (**Rationale**),
- és mi következik belőle (**Consequences**).

A mappa: `docs/private/20-decisions/`. A projekt szabálya (CLAUDE.md): minden olyan
döntés, amelynek volt valódi alternatívája, számozott ADR-t kap, mert a professzor a
pull requestekben meg fogja kérdezni, hogy "miért így".

## 2. A státuszok

Minden ADR tetején van egy `status:` sor:

| Státusz | Jelentése | Szerkeszthető? |
|---|---|---|
| `proposed` | javaslat, még nem döntöttük el | **igen, szabadon** |
| `accepted` | eldöntöttük | **nem írjuk át** |
| `superseded` | egy újabb ADR felülírta | nem, csak rámutat az újra |

Például:

- Az **ADR-0003** (AGPL-licenc) napokig `proposed` volt, amíg a professzor válaszára
  vártunk. 2026-09-10-én lett `accepted`.
- Az **ADR-0007** most `proposed`, ezért szerkesztettük is (a professzor 09-12-i
  üzenetét beleírtuk), és a tervező ügynök is át fogja dolgozni.

## 3. Miért nem írjuk át az elfogadottat

Nem technikai korlát: bármelyik fájlt át tudnám írni. Ez a **projekt szabálya**, és jó
oka van.

Egy döntés az akkori tudással születik. Ha egy elfogadott ADR-t utólag csendben
átírnánk, eltűnne, hogy **mit tudtunk akkor**, és miért tűnt jónak a döntés. Pedig a
professzor pontosan erre kíváncsi. És te is: fél év múlva nem fogsz emlékezni, miért
választottunk valamit.

Hasonlat: egy aláírt ülési jegyzőkönyvet sem írnak át, ha később kiderül, hogy a döntés
rossz volt. Új jegyzőkönyvet írnak, amely hivatkozik a régire. A git előzmények is
ugyanígy működnek: nem írjuk át a régi commitokat, új commitot teszünk rájuk.

## 4. Mit lehet mégis tenni egy elfogadott ADR-rel

- **Új ADR, amely felülírja** (`supersedes: ADR-000X`). A régi státusza `superseded`
  lesz. Ez a tiszta út, ha maga a döntés változik.
- **Kimeneti napló hozzáfűzése** ("Outcome log"). Ha a döntés áll, csak egy
  következménye vagy kockázatcsökkentő lépése változott. Az ADR-0004 így jegyezte fel,
  hogyan alakultak a mitigációi.
- **Fejléc-megjegyzés**. Az ADR-0006 tetején egy doboz jelzi, hogy a döntés más lett,
  mint a javaslat, és hogy a kontextus egy pontja elavult. Az eredeti szöveg viszont
  olvasható maradt.

## 5. Ki dönt

**Te döntesz** (a professzorral egyeztetve). Claude és az ügynökök javasolnak:
lehetőségeket írnak le, és ajánlást adnak. Amikor azt írtam, hogy "a döntés a tiéd",
nem azt jelentette, hogy nem tudom átírni a fájlt. Azt jelentette, hogy egy `proposed`
ADR-t nem teszek `accepted`-dé helyetted.

Egy ADR elfogadásához elég annyit írnod: "ADR-0007 elfogadva" (vagy "így és így
módosítva elfogadva"). Ezután átállítom a státuszt, beírom a dátumot, és frissítem az
indexet.

## 6. Tévhitek

**"Ha egy ADR rossznak bizonyul, szégyen, és javítani kell benne."** Nem. A rossznak
bizonyult döntés egy új ADR-rel válik láthatóvá, és pont ez mutatja, hogy a munka
tanult. Ez erősség a védésen.

**"Minden apró döntéshez ADR kell."** Nem, csak ahhoz, aminek volt valódi alternatívája,
és amire a professzor rákérdezhet.

**"A proposed ADR már érvényes."** Nem. Amíg `proposed`, addig csak javaslat. Lehet
szerinte dolgozni, de még változhat.
