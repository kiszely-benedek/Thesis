"""A gráf séma csomagja.

Ez tartja karban azt, amit a generátor kienged és a splitter feldarabol: a
csomópont- és relációtípusokat, a rajtuk kötelező tulajdonságokat, és az ezt
ellenőrző függvényeket (`docs/private/40-design/plant-generator.md` §4). A
csomag nem importál `pydexpi`-t, és nem tud a `benchmark` csomagról — ez utóbbi
építi rá magát, nem fordítva.
"""

from __future__ import annotations
