---
topic: OPEN100 rendszerkódok — ESS, CND, RCS és a többi
status: draft
related: [ADR-0005, 40-design/open100-annotation.md, pid-lapkozi-csatlakozok.md, sheets.py]
---

# Az OPEN100 rendszerkódjai: mit jelent az ESS, a CND, az RCS és a többi?

## Miért van ez

Egy erőmű P&ID-sorozatában minden lap egy **rendszert** rajzol meg, és minden rendszernek van egy két–négy betűs kódja. Ez a kód mindenhol ott van: a lap fejlécében, a berendezések azonosítójában (`CND-TK-165`: a kondenzátumrendszer 165-ös tartálya), a csővezetékek számában (`SIZE-CND-165117-...`) és a lapszéli csatlakozók zászlóin (`CND PID 160-1`). Aki nem tudja, hogy a CND a kondenzátum, az egyetlen zászlót sem tud értelmezni — csak betűket lát. Ez a jegyzet a szótár, plusz az a történet, amiben a rendszerek összeérnek.

## Az alapgondolat

Az OPEN100 az Energy Impact Center nyílt forrású, 100 MWe-os **nyomottvizes reaktor** (PWR) terve ([open-100.com](https://www.open-100.com/introduction)). Egy PWR két vízkörből áll, amelyek a gőzfejlesztőben érnek össze, de nem keverednek:

- **Primer kör.** A reaktorban felmelegített, nagy nyomású víz a gőzfejlesztő csövein át leadja a hőt, majd a főkeringtető szivattyúk visszanyomják a reaktorba. Radioaktív; minden, ami hozzáér, a "nukleáris" oldalhoz tartozik.
- **Szekunder kör.** A gőzfejlesztő másik oldalán víz forr fel, a gőz a turbinára megy, onnan a kondenzátorba, a kondenzátumot a tápvízszivattyúk visszanyomják a gőzfejlesztőbe. Ez egy közönséges hőerőmű köre.

A kódok ezt a két kört és a köréjük épített segédrendszereket nevezik meg. A táblázatban az áll, ahogy a rajzokon **ténylegesen** nyomtatva van; a "mit láttunk" oszlop a lapok berendezés-jegyzékéből és zászlóiból jön, nem tankönyvből.

| Kód a rajzon | Rajzszám | Lap a 12-ből | Mi ez | Mit láttunk a rajzokon |
|---|---|---|---|---|
| **RCS**, RC | PID 100 | 5, 6 | Reaktorhűtő rendszer — a primer kör | RCS-XR-100 reaktortartály, RCS-SG-101 gőzfejlesztő, RC-P102A/B (= RCS-PU-102A/B) főkeringtető szivattyúk, RCS-V-103 térfogatkiegyenlítő, RCS-VE-104 lefúvató tartály |
| **CVCS** | PID 110 | 10 | Térfogat- és vegyszerszabályozás — a primer víz tisztítása, pótlása, bórsav-adagolás | CVCS-HX-110/111 hőcserélők, CVCS-FL-112A/B szűrők, CVCS-ION-114A/B ioncserélők, CVCS-PU-115/117 töltőszivattyúk, CVCS-VCT-118 tartály |
| **RHRS**, RHR | PID 120 | 11 (1. lap), 9 (2. lap) | Maradványhő-elvonás — leállás után a fűtőelemek bomláshőjét viszi el | RHR-HX-121A/B hőcserélők, RHR-PU-120A/B szivattyúk |
| **SWS** | PID 130 | — | Üzemi (nyers) hűtővíz — a végső hőnyelő | csak zászlókon |
| **MSS** | PID 140 | 0 | Frissgőz — a gőzfejlesztőből a turbina felé | RCS-SG-100 gőzfejlesztő, MSS-XSS-140 túlhevítő |
| **ACC** | PID 150 | 1 | Légkondenzátor — a turbinából jövő gőzt ventilátoros hőcserélők csapják le | ACC-AC-150 légkondenzátor, ACC-PU-151..153 szivattyúk |
| **CND**, COND | PID 160 | 2 | Kondenzátum — a lecsapott víz gyűjtése, előmelegítése, gáztalanítása | CND-TK-160 tároló, CND-HTR-161/166 előmelegítők, CND-PU-162..164 szivattyúk, CND-TK-165 gáztalanító tartály, CND-FLT-167 polírozó |
| **FWS** | PID 170 | 3 (2. lapja hiányzik) | Tápvíz — a kondenzátumot nagy nyomáson a gőzfejlesztőbe nyomja | FWS-PU-170A/B tápszivattyúk, FWS-HTR-170 nagynyomású előmelegítő |
| **ESS**, ES | PID 180 | 4 | Megcsapolt gőz — a turbinából elvett gőz, ami a tápvizet melegíti | ESS-HTR-180 gőzhűtő ("de-superheater") |
| **HPSD**, HPD | PID 190 | — | Nagynyomású gőzcsapadék elvezetés | csak zászlókon |
| **WTS** | PID 200 | — | Vízkezelés — pótvíz előállítása | csak zászlókon (`MAKE-UP WATER`) |
| **ACW** | PID 210 | 7, 8 | Segédhűtővíz — zárt hűtőkör a szivattyúk és hőcserélők hűtésére | ACW-AXC-210 hűtő, ACW-PU-211A/B/C szivattyúk, ACW-TK-212 tartály |
| **TBS**, TURB | PID 240 / 250 | — | Turbina, illetve turbina-kipufogás | csak zászlókon |
| **PDS** | PID 260 | — | Üzemi lefolyók | csak zászlókon |
| **WPS** | PID 270 | — | Hulladékvíz-feldolgozás | csak zászlókon |
| **WSS**, WWS, WS | PID 290 | — | Vízmintavétel — vegyi ellenőrzéshez | csak zászlókon |
| — | PID 300 | — | Pótvíz (`MAKE-UP WATER`, kód nélkül) | egy zászló (10/193) |
| **RWS**, CAS | PID 320 | — | Radioaktív hulladék, illetve vegyszeradagolás — ugyanaz a rajzszám két névvel | csak zászlókon |

A vastag alak a leggyakoribb írásmód; a mellette állók ugyanannak a rendszernek a rajzokon **ténylegesen előforduló** változatai. `ES` és `ESS`, `CND` és `COND`, `RHR` és `RHRS`, `WSS`/`WWS`/`WS` egy-egy rendszer — a rajzoló nem volt következetes, és ezt el kell fogadni, nem kijavítani.

## Kidolgozott példa: a víz útja a 12 lapon

Kövessük egy csepp vizet a szekunder körben, a kódokkal:

1. **RCS (5. lap)** — a gőzfejlesztő primer oldalán a reaktorvíz leadja a hőt. A szekunder oldalon gőz keletkezik, és a `MSS PID 140-1` zászlón kilép.
2. **MSS (0. lap)** — a frissgőz a túlhevítőn át a turbinához megy (`TBS PID 240-1`, a rajz nincs meg). Egy ága a főgőz-megkerülő vezeték az `ACC PID 150-1` felé (0/83 ↔ 1/3 pár).
3. **TBS/TURB (nincs meg)** — a turbina. A kipufogó gőz a `TURB PID 250-1` zászlón jön vissza az 1. lapra.
4. **ACC (1. lap)** — a légkondenzátor lecsapja a gőzt. A kondenzátum a `COND PID 160-1` zászlón lép ki (1/73 ↔ 2/16 pár, vezetékszám 150104).
5. **CND (2. lap)** — tárolás, előmelegítés, gáztalanítás. Innen megy a `FWS PID 170-2` felé (a 170-es rajz 2. lapja hiányzik, ezért lógó).
6. **FWS (3. lap)** — a tápszivattyúk visszanyomják a vizet a gőzfejlesztőbe (`FWS PID 170-2`, szintén hiányzó lap). A kör bezárul.

Közben: az **ESS (4. lap)** a turbinából megcsapolt gőzzel fűti a CND előmelegítőit — ezért van a 4. lapon két `CND PID 160-1` bejövő és a 2. lapon egy `ESS PID 180-1` kimenő zászló, azonos `165117` vezetékszámmal. Az **ACW (7–8. lap)** zárt körben hűti a főkeringtető szivattyúk hőcserélőit (`RCS PID 100-2` zászlók a 8. lapon, `ACW PID 210-2` zászlók a 6. lapon). A **CVCS (10. lap)** és az **RHRS (9., 11. lap)** a primer körre csatlakozik, ezért a zászlóik `RCS PID 100-1`-re és egymásra mutatnak. A **WSS**, **WPS**, **PDS**, **RWS** zászlók mindenhonnan kifelé mutatnak, olyan rajzokra, amelyek nincsenek meg: ezek a "nem tudjuk" tesztesetek.

## Hová illik

A `sheets.py` ezt a táblázatot tartja karban: fájl → rajzszám → rendszernév (`SHEETS`), és a hivatkozott, de hiányzó rajzok listáját (`KNOWN_ABSENT`). A zászlón olvasott `service` mező mindig **a másik oldal** rendszerkódja: egy bejövő zászlón azé a rendszeré, ahonnan a cső jön, egy kimenőn azé, ahová megy. Ezért a `service` nem azonosít csövet — arra a vezetékszám van (lásd a lapközi csatlakozókról szóló jegyzetet).

## Tipikus félreértések

- **"Az ES és az ESS két különböző rendszer."** Nem. Ugyanaz a rendszer, két írásmóddal, két különböző lapon. A rajzszám (180) dönt.
- **"A kód a csövön azt mondja, hová megy."** Nem. A vezetékszám előtagja azt mondja, **melyik rendszer tulajdona** a cső azon a lapon. A `SIZE-ACW-211157` a 8. lapon ACW-vezeték, pedig az RCS 100-2 lapjára megy.
- **"Ha egy rendszernek nincs lapja, hiba van."** Nem. A PID2Graph csak 12 lapot vett át az OPEN100-ból; a hivatkozott 130, 190, 200, 240, 250, 260, 270, 290, 300, 320 rajzok léteznek, csak nem a mieink.
- **"A 320 két rendszer."** Nem tudjuk. Ugyanazt a rajzszámot egyszer `RWS / RAD WASTE SYSTEM`, egyszer `CAS / CHEMICAL ADDITION SYSTEM` néven hivatkozzák. Lehet két rendszer egy épületben, lehet elírás; a rajz nélkül eldönthetetlen, és a mérésnek ez épp jó: mindkét zászló lógó.

## Ha egy dolgot olvasol el

[OPEN100 — áttekintés](https://www.open-100.com/introduction): a tervező szervezet saját leírása arról, milyen erőműről szólnak ezek a lapok.
