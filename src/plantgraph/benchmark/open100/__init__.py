"""Processing the 12 real OPEN100 P&ID drawings, from connector search to answer key.

A P&ID (piping and instrumentation diagram) is the kind of engineering drawing this
whole project reasons about. In two stages: `corpus.py`/`extract.py`/`crops.py` find
the off-page connectors — the labelled markers a drawing uses to say "this pipe
continues on another sheet" — and crop images of them for reading (stage 1);
`annotations.py` and `manifest.py` turn the read-off labels into the final
`SplitManifest`, the answer key describing how the sheets fit together (stage 2).
See `docs/private/40-design/open100-annotation.md`.
"""
