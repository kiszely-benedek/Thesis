# Git-történet átírása és a force-push — mit csinál, és mit *nem* csinál

*Tanulónote, 2026-09-19. Azért íródott, mert a repót publikussá tetted, és a teljes
előzményt át kellett írni.*

---

## 1. Miért nem elég egy új commit?

Ez a legfontosabb mondat az egészben:

> **A git soha nem felejt magától. Egy új commit nem törli a régit — csak ráteszi egy réteget.**

Ha ma törölsz egy fájlt és commitolod, a fájl **továbbra is ott van** a tegnapi commitban.
Bárki, aki klónozza a repót, megkapja az egész előzményt, és egyetlen paranccsal
visszanézheti:

```powershell
git show <régi-commit>:torolt_fajl.md
```

Ezért volt kevés korábban a „kiveszem a Gamma6635-öt a commit üzenetből” lépés: az új
üzenet melléírt egy újat, de a régi objektum a repóban maradt.

---

## 2. Mi az a commit, és miért változik meg az összes azonosító?

Egy commit tartalma: a fájlok pillanatképe + a szerző + a dátum + az üzenet +
**a szülő commit azonosítója**. Ebből az egészből készül egy SHA-1 ujjlenyomat — ez a
`1cbb019…` szerű azonosító.

Következmény: **ha bármit megváltoztatsz egy régi commitban, annak az azonosítója
megváltozik — és mivel minden utána jövő commit hivatkozik a szülőjére, azoké is.**
Egy láncszem cseréje az egész láncot újraönti.

Ezért lett a 14 commitból 10 új azonosítójú commit. (Négy eltűnt: ezek *csak* a
`docs/` mappát módosították, és miután azt kivettük az előzményből, üresek lettek.)

---

## 3. A `git filter-repo`

Ez az eszköz végigolvassa az egész előzményt az első committól, és commitonként
újraírja. Amit most kért tőle a munka:

| Kérés | Mit csinált |
|---|---|
| `--invert-paths --path docs/ …` | minden commitból kivette a `docs/`, `CLAUDE.md`, `.claude/`, `.mcp.json` útvonalakat — **visszamenőleg is** |
| `--blob-callback` | minden fájl *tartalmát* átfuttatta egy Python-függvényen (ez cserélte pl. az „Opus-újraolvasás” szót „újraolvasás”-ra minden régi verzióban) |
| `--message-callback` | minden commit *üzenetét* átfuttatta (ez vágta le a `Co-Authored-By:` sorokat) |

Fontos: a filter-repo egy **friss, tükör-klónon** futott
(`git clone --mirror`), nem a munkakönyvtáradon. Így ha elrontja, a te mappád érintetlen
marad. Csak az ellenőrzés után került vissza az eredmény.

---

## 4. A force-push — pontosan mit jelent

Normál `git push` esetén a git megköveteli, hogy amit felküldesz, az a szerveren lévő
állapot **folytatása** legyen. Az átírt előzmény nem folytatása semminek: teljesen új
azonosítói vannak. A normál push ezt visszautasítja.

A `--force` (pontosabban a biztonságosabb `--force-with-lease`) azt mondja a szervernek:

> „Ne fűzd hozzá. **Dobd el, amit a `main` ágon tartasz, és mutasson ettől kezdve erre.**”

### Amit a force-push megtesz

- A GitHubon a `main` ág mostantól az új, tiszta 10 commitra mutat.
- A repó weblapján, a commit-listában, a fájlböngészőben **csak az új előzmény látszik**.
- A közreműködők (contributors) listája a `main` ágból számolódik újra — ezért tűnik el
  a „claude" és a „Gamma6635" is.

### Amit a force-push **nem** tesz meg

Ez a rész a lényeg, és ezt szokták elrontani:

1. **A régi objektumok nem törlődnek azonnal a szerverről.** Elveszítik a nevüket (nem
   mutat rájuk ág), de a GitHub még kiszolgálja őket, ha valaki tudja a régi SHA-t:
   `https://github.com/<user>/<repo>/commit/<régi-sha>` még működik. Ezt a GitHub a saját
   ütemezése szerint takarítja ki (garbage collection) — nem azonnal, és nem garantált
   határidővel.
2. **Aki korábban klónozta vagy forkolta, annál a régi előzmény megmarad.** A force-push
   az ő gépükön semmit nem változtat.
3. **Amit valaki elmentett vagy amit egy kereső beindexelt, az elment.** A publikálás
   egyirányú utca: visszavonni csak azt lehet, amit még senki nem látott.
4. **Más felületek külön élnek.** Pull request címek, issue-k, kommentek, release-jegyzetek,
   a wiki — ezeket a git-előzmény átírása *nem* érinti. Külön kell átnézni őket.
   (Ebben a repóban mindegyik üres volt, tehát nem volt mit takarítani.)

### Ha valaki más is dolgozik az ágon

A force-push az ő következő `git pull`-jukat elrontja: divergáló előzményt kapnak. Nekik
újra kell klónozniuk, vagy `git fetch` + `git reset --hard origin/main` kell. Egyszemélyes
repónál ez nem gond — csapatmunkában előre szólni kell.

---

## 5. Mit jelent a „biztonsági háló" itt

Mielőtt bármi átírás történt, két mentés készült a scratchpad-be:

- egy `.tar.gz` a teljes mappáról, a `.git` könyvtárral együtt;
- egy `git bundle`, ami az összes ref-et és objektumot tartalmazza egyetlen fájlban.

A bundle-ből a régi állapot bármikor visszaállítható:

```powershell
git clone <bundle-fájl> visszaallitott-repo
```

Ez a szabály általánosan is igaz: **előzmény-átírás előtt mindig készíts bundle-t.**

---

## 6. Miért `.git/info/exclude`, és nem `.gitignore`?

A tooling-fájlok (`CLAUDE.md`, `.claude/`, `.mcp.json`) és a `docs/` mappa a gépeden
maradtak, csak a git nem követi őket többé.

Kézenfekvő lenne beírni őket a `.gitignore`-ba — **de a `.gitignore` maga is commitolt
fájl.** Ha abban ott áll, hogy `.claude/` és `CLAUDE.md`, akkor pontosan azt árulja el,
amit el akartunk tüntetni.

A `.git/info/exclude` ugyanúgy működik, de **soha nem kerül be a repóba**: a `.git`
könyvtáron belül él, csak a te klónodban. Erre való.

---

## Összefoglaló

| Fogalom | Egy mondatban |
|---|---|
| commit SHA | a tartalom + a szülő ujjlenyomata — ezért terjed a változás előre az egész láncon |
| `git filter-repo` | végigmegy az összes committon és újraírja őket egy szabály szerint |
| force-push | „dobd el, amit tartasz, és mutass ide" — nem hozzáfűzés, hanem csere |
| elérhetetlen objektum | névtelenül, de még kiszolgálhatóan ottmaradt régi adat a szerveren |
| `git bundle` | az egész repó egy fájlban, visszaállításhoz |
| `.git/info/exclude` | lokális `.gitignore`, ami maga nem kerül be a repóba |
