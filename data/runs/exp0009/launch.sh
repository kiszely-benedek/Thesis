#!/bin/sh
# Launch wrapper for a detached run (README, "Start"): sets the environment run_all.sh needs, then runs it.
#   bash.exe -l C:/path/to/repo/data/runs/exp0009/launch.sh [run_all.sh options, e.g. --from P1b]
# E10_NEO4J_HOME is the Neo4j server's home folder (order: the environment, a line in the git-ignored .env, then
# the Neo4j Desktop folder that EXP-0008's launch.sh names). Output is appended to data/runs/exp0009/run_all.log.
set -eu
cd "$(dirname "$0")/../../.."

if [ -z "${E10_NEO4J_HOME:-}" ] && [ -f .env ]; then
  E10_NEO4J_HOME=$(sed -n 's/^E10_NEO4J_HOME=//p' .env | tail -n 1 | tr -d '\r"')
fi
if [ -z "${E10_NEO4J_HOME:-}" ]; then
  E10_NEO4J_HOME="${USERPROFILE:-$HOME}/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
fi
if [ ! -d "$E10_NEO4J_HOME" ]; then
  echo "ERROR: expected the Neo4j home at $E10_NEO4J_HOME, found no such folder (set E10_NEO4J_HOME)" >&2
  exit 2
fi
export E10_NEO4J_HOME

exec sh data/runs/exp0009/run_all.sh "$@" >> data/runs/exp0009/run_all.log 2>&1
