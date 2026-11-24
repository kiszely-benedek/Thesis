#!/bin/sh
# The readiness checklist before P0, as far as a program can check it. Read-only: starts no stage, writes nothing,
# makes no paid call.
#   sh data/runs/exp0009/readiness.sh [--smoke-passed <smoke root>/SMOKE_PASSED] [--no-neo4j] [--no-network]
set -eu
cd "$(git rev-parse --show-toplevel)"
exec "${E10_PYTHON:-.venv/Scripts/python}" -m plantgraph.qa.exp0009.readiness "$@"
