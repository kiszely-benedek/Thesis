# Comment audit — `src/plantgraph/`, 2026-09-13

Scope: `src/plantgraph/` in full (`benchmark/` including `open100/`, `graph/`), following `.claude/skills/python-comments/SKILL.md`. Comments and docstrings only, zero logic changes (proven below). Report prose in English per the task instructions; quoted comments are Hungarian as written in the code.

## Comment Audit Report

### Summary

- **Files analyzed:** 23 (`src/plantgraph/**/*.py`)
- **Total LOC:** 3,174 (all 23 files individually under the 400-line cap; largest is `benchmark/models.py` at 361)
- **Total comments:** 264 (docstrings: 159, inline `#`: 105 — counted with `ast`/`tokenize`, see `Coverage Metrics`)
- **Type distribution (sampled across the codebase):** Type 1 (Function): 159 docstrings, all present and Google-style. Type 2 (Design): present at module level in nearly every file (e.g. `models.py`, `strategies.py`, `generator.py` module docstrings explain *why this split*, not just *what*). Type 3 (Why): the majority of inline `#` comments, e.g. `strategies.py:189` ("a rng.random() mindig lefut... ez tartja a hívási sorrendet azonosnak"). Type 4 (Teacher): frequent and strong, e.g. `open100/extract.py` module docstring explaining GraphML has no text, `models.py` `BoundingBox`/`ConnectorObservation` docstrings explaining P&ID domain terms. Type 5 (Checklist): rare, not needed — no function in scope has an order-dependent multi-step sequence that isn't already broken into named private methods (e.g. `generator.py`'s `_GenerationState` uses named methods per step instead of inline numbering). Type 6 (Guide): used exactly where warranted — `generator.py`'s `_GenerationState` uses `# ---- lépés N ----` section headers because the class is long and the design note (`plant-generator.md` §3.3) itself is structured in five numbered steps. Type 7 (Trivial): **0 found**. Type 8 (Debt): **0 found** (`TODO`/`FIXME`/`HACK` grep matched only two false positives — literal `"FCV XXX"` and `"műszer XXX"` inside quoted drawing-label text in `open100/annotations.py`, not debt markers). Type 9 (Backup): **0 found** (grep for commented-out `def`/`class`/`return`/`import`/`self.` patterns found nothing in `src/` or `tests/`).
- **Quality score: 9/10.** This codebase had already been through a prior comment pass (visible from commit history and the density/consistency of Type 2–4 comments). The only gap found was three completely empty `__init__.py` files with no module docstring.

### Critical Gaps

- [x] `src/plantgraph/__init__.py` — top-level package, 0 bytes — Missing Type 1 (module) docstring — the package had no statement of what it is, violating the project's own rule ("each [folder] with a clear job and an `__init__.py` that says what it is", `.claude/agents/coder.md`). **Fixed.**
- [x] `src/plantgraph/benchmark/__init__.py` — 0 bytes — same gap. **Fixed.**
- [x] `src/plantgraph/benchmark/open100/__init__.py` — 0 bytes — same gap. **Fixed.**
- Note: `ruff`'s configured rule set explicitly ignores `D104` (missing docstring in public package), so this was not a lint failure — it is a readability gap the linter does not catch, which is exactly what a human audit is for.

### Issues Found

#### Negative Comments (fix or remove)

None found. No Type 7 (trivial), Type 8 (debt/TODO), or Type 9 (commented-out code) comments exist anywhere under `src/plantgraph/` or `tests/`.

#### Outdated Comments

None found. Spot-checked comments that reference specific behaviour (e.g. `strategies.py`'s claim that `modularity` uses Louvain communities, `connectors.py`'s claim that `send_to` maps to `PIPE`) against the code they annotate — all accurate.

#### Quality Issues

- No quality issues found in the 20 non-empty files. Docstrings consistently: state purpose in the summary line, document argument *semantics* rather than repeating type hints (e.g. `BoundingBox.expanded`'s docstring explains *why* the padding is needed — the line number sits beside the box, not inside it — rather than restating "expands the box"), and cross-reference the design note and section number they implement (e.g. `plant-generator.md §3.3`, `splitter.md` "nyitott 3. kérdés").
- Eight private helpers have no docstring: `generator.py:_GenerationState.__init__`, `generator_models.py:_check_equipment_range`, `generator_models.py:_check_equipment_weights`, `models.py:BoundingBox._check_ordering`, `models.py:IdentityGroup._check_not_alone`, `splitter.py:_strategy`, `splitter.py:_validate_has_equipment`, `open100/stage2.py:_summary`. All are private (leading underscore), all have names that already say what they do (a `_check_ordering` validator on `BoundingBox` needs no further explanation), and per the coder rule "private helpers need one only if the name does not already say it" none of these warrant one. Not treated as gaps.

### Coverage Metrics

| Scope | With Docstring | Without | Coverage |
|-------|---------------|---------|----------|
| Modules | 20 → 23 (after fix) | 3 → 0 | 87% → **100%** |
| Classes | 32 | 0 | 100% |
| Public functions/methods | 104 | 0 | 100% |
| Private functions/methods (docstring optional) | — | 8 | all self-explanatory by name, see above |

(Counted with `ast.get_docstring` over every module/class/function in `src/plantgraph/**/*.py`; script kept in the session scratchpad, not committed.)

### Recommendations

1. **Priority 1 (done):** Add module docstrings to the three empty `__init__.py` files so every package states its job, per the project's own folder-organization rule.
2. **Priority 2 (no action needed):** Nothing else qualifies as a gap. The codebase already applies the taxonomy correctly — Design comments at module level, Why comments on non-obvious branching (RNG call ordering, cyclic-graph fallbacks, deterministic sort-before-iterate patterns), Teacher comments glossing P&ID domain terms for a reader who knows Python but not process engineering, and Guide comments only where a module is long enough to need them.
3. **Priority 3 (out of scope, noted for the log):** `tests/` was checked for negative types only, per instructions — none found. Test comments there are already Type 3/4 quality (e.g. `test_generator_integration.py`'s comment on invariant 8 explaining *why* the test must not be "fixed" by tuning the generator).

### Comment Style

- **Detected style:** Google (matches `pyproject.toml`'s `[tool.ruff.lint.pydocstyle] convention = "google"`, with `D203`/`D213` ignored to avoid the blank-line-before-summary conflict).
- **Consistency:** Fully consistent across all 23 files — `Args:`/`Returns:`/`Raises:` keywords in English, prose in Hungarian, one-line docstrings for self-explanatory functions, multi-line for anything with a non-obvious edge case or domain term.
- **Recommendation:** No change. Keep matching this style for future modules.

### Debt markers found (none actionable)

No `TODO`/`FIXME`/`HACK`/`XXX` debt comments exist in `src/plantgraph/`. The only `XXX` matches are literal placeholder text quoted from drawing labels inside `open100/annotations.py` data rows (`"FCV XXX"`, `"minden műszer XXX"`) — these are provenance data, not code debt, and were left untouched per the per-row-comment exclusion for that file.

---

## Changes applied

Write mode ran over the full scope. Of the 23 in-scope files, **20 needed no change** — they already carried Type 1–6 comments of good quality, matched Google docstring style, and contained no negative types. Only the three empty `__init__.py` files were edited:

| File | Type | Change | Why |
|---|---|---|---|
| `src/plantgraph/__init__.py` | 1 (Function/module) | Added a module docstring naming the two sub-packages (`graph`, `benchmark`) and pointing to `docs/private/40-design/`. | The file was 0 bytes; the package stated no job, violating the project's own folder-organization rule. |
| `src/plantgraph/benchmark/__init__.py` | 1 (Function/module) | Added a module docstring summarising the generator → splitter → OPEN100 pipeline and cross-referencing `models.py` for the shared manifest contract. | Same gap; this is the busiest sub-package and benefits most from an orientation docstring. |
| `src/plantgraph/benchmark/open100/__init__.py` | 1 (Function/module) | Added a module docstring describing the two annotation stages (geometry extraction, then label-based manifest building) and pointing to the design note. | Same gap. |

No other file was touched. No Type 7/8/9 comments existed to remove. No docstring was rewritten, since none was missing, trivial, or inaccurate outside the three files above.

**Verification of zero logic change:** every in-scope `.py` file was copied to a scratchpad snapshot before editing. After editing, a script parsed both versions with `ast`, stripped the first statement of every module/class/function body when it was a string constant (i.e. removed all docstrings), and compared `ast.dump()` of the remainder. Output:

```
OK — 23 files compared, zero logic change (docstrings excluded).
```

(The first run correctly caught a mistake: my first draft of the three new `__init__.py` files also added `from __future__ import annotations`, which is a real statement, not a comment — the script flagged all three as changed. I removed the import, keeping only the docstring, and the second run passed.)

## Test results after the pass

```
uv run --offline pytest -q
175 passed in 0.63s
```

```
uv run --offline ruff check .
All checks passed!
```

```
uv run --offline ruff format --check src tests
34 files already formatted
```

```
uv run --offline mypy
Success: no issues found in 23 source files
```

All four match or exceed the pre-pass baseline (175 tests passed, ruff/format/mypy clean before this session started).

## File line counts (files touched)

- `src/plantgraph/__init__.py` — 6 lines
- `src/plantgraph/benchmark/__init__.py` — 8 lines
- `src/plantgraph/benchmark/open100/__init__.py` — 7 lines

All well under the 400-line cap.
