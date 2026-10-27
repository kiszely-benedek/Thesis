"""EXP-0007 tooling: the v2 re-measurement's guards, caps, pilot and dev-check report (ADR-0060).

Everything here is free of paid calls. The run scripts in `data/runs/exp0007/` call these commands;
the logic lives here so that it is tested. Nothing here is on the system-side path list of the
unchanged-path check (`paths.py`): changing it does not change the system that answers questions.
"""
