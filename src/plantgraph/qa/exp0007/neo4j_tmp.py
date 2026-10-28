"""Dropping the temporary Neo4j database a tuning script loaded plants into."""

from __future__ import annotations

from neo4j import GraphDatabase

from plantgraph.qa.exp0007.hygiene import require_database
from plantgraph.store.neo4j_settings import from_env

#: Databases a script must never drop: the user's plant database and the server's admin database.
_PROTECTED = ("neo4j", "system")


def require_droppable(name: str) -> str:
    """The database name, if it is a plain temporary name.

    Raises:
        ValueError: no name, a malformed one, or one of the protected databases.
    """
    require_database(name, is_plant_database=True)  # name syntax only; protection is checked here
    if name in _PROTECTED:
        raise ValueError(f"refusing to drop {name!r}: only a temporary database may be dropped")
    return name


def drop_database(name: str) -> None:
    """`DROP DATABASE IF EXISTS` for a temporary database.

    Raises:
        ValueError: see `require_droppable`, or the Neo4j settings are not in the environment.
    """
    settings = from_env()
    if settings is None:
        raise ValueError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD, found some unset")
    safe = require_droppable(name)  # spliced into the command (not a parameter), so it was checked
    driver = GraphDatabase.driver(
        settings.uri, auth=(settings.username, settings.password.get_secret_value())
    )
    try:
        with driver.session(database="system") as session:
            session.run(f"DROP DATABASE `{safe}` IF EXISTS WAIT").consume()
    finally:
        driver.close()
