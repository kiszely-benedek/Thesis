# data

Everything the demo and the experiments read. Committed so that a fresh clone can rerun them; Neo4j itself is not
stored here — `python -m plantgraph.ingest` (or the demo's plant switch) loads a plant from its `ingest.json`.

| Path | Holds |
|---|---|
| `external/C01V04-VER.EX01.xml` | the DEXPI reference P&ID (EX01), from DEXPI "Public Example PIDs" (gitlab.com/dexpi/TrainingTestCases), CC BY 4.0 |
| `external/chatpid_ex01_qa.jsonl` | ChatP&ID's 19 EX01 questions with their reference answers, transcribed from arXiv:2603.22528v1, App. Table 1 |
| `runs/cv1/neo4jplant/<id>/ingest.json` | the dev plants D100 and D1000 (generator settings, sheets, resolution) |
| `runs/cv1/questions/`, `qfull/`, `qfree/`, `q5/` … | benchmark question sets with gold answers |
| `runs/cv1/runs/<run id>/` | every dev run: frozen run config, answers, per-call log |
| `runs/cv1/cascade_report*/`, `infra/`, `route01/` | reports built from those runs |
| `runs/cv1/drawings/` | the drawing PDFs the demo shows |
| `runs/cv1/demo/` | demo config and example questions |
| `runs/sealed/` | the sealed test (EXP-0002) on the held-out plants H100/H1000: questions, runs, report |
| `runs/exp0001/` | the single-sheet experiment (EXP-0001): size ladder and EX01 |
| `runs/pilot/` | the first paid pilot |
| `**/*.sqlite` | LLM response caches: a run replays from them with no paid call |
| `runs/cv1/*.sh` | the shell scripts the runs were started with |

Row by row, the numbers built from these files are in `docs/private/30-experiments/_results.md`.
