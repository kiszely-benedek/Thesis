#!/bin/sh
# Launch wrapper for a detached run (README, "Start"): sets the environment run_all.sh needs, then runs it.
#   bash.exe -l C:/path/to/repo/data/runs/exp0008/launch.sh [run_all.sh options, e.g. --from M5]
# Use forward slashes in the path. The output is appended to data/runs/exp0008/run_all.log.
#
# E9_NEO4J_HOME is the Neo4j server's home folder (M7 reads its store sizes). Order of precedence:
# the environment, a line `E9_NEO4J_HOME=...` in the git-ignored .env, then the Neo4j Desktop folder that
# data/runs/exp0007/run_infra_v2.sh and data/runs/cv1/run_infra.sh already name.
set -eu
cd "$(dirname "$0")/../../.."

if [ -z "${E9_NEO4J_HOME:-}" ] && [ -f .env ]; then
  E9_NEO4J_HOME=$(sed -n 's/^E9_NEO4J_HOME=//p' .env | tail -n 1 | tr -d '\r"')
fi
if [ -z "${E9_NEO4J_HOME:-}" ]; then
  E9_NEO4J_HOME="${USERPROFILE:-$HOME}/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
fi
if [ ! -d "$E9_NEO4J_HOME" ]; then
  echo "ERROR: expected the Neo4j home at $E9_NEO4J_HOME, found no such folder (set E9_NEO4J_HOME)" >&2
  exit 2
fi
export E9_NEO4J_HOME

exec sh data/runs/exp0008/run_all.sh "$@" >> data/runs/exp0008/run_all.log 2>&1
