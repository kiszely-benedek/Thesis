#!/bin/sh
# The readiness checklist of review-fixes §5.4, as far as a program can check it. Read-only: starts no stage,
# writes nothing, makes no paid call.
#   sh data/runs/exp0008/readiness.sh [--smoke-passed <smoke root>/SMOKE_PASSED] [--no-neo4j] [--no-network]
# Exit code 1 if any item failed; items only a person can answer print as [HAND].
set -eu
cd "$(git rev-parse --show-toplevel)"
exec "${E9_PYTHON:-.venv/Scripts/python}" -m plantgraph.qa.exp0008.readiness "$@"
