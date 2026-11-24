"""V2T-B: the revision of the frozen V2T-A2 that reads valve positions and names untagged valves.

Every file here is new (ADR-0067). Nothing under `qa/` that V2T-A2 runs is edited, so the frozen
arm stays byte-identical; importing this package changes no module of it (tested in
`tests/v2tb/test_import_isolation.py`). The design is `40-design/v2t-b-system-revision.md`.

Two ideas carry the package:

- a B corpus keeps the valve property `operating_position` (`visible.py`, `schema_text_b.py`,
  `primer_b.py`), and the model may answer with a **descriptor** for a valve that prints no tag
  (`descriptor.py`, `final_answer_b.py`);
- the scorer resolves every answered item to plant nodes and compares node sets (`scoring_b.py`).
"""
