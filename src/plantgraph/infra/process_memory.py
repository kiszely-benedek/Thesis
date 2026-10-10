"""Memory readings of this process and of the Neo4j server, for the infrastructure probe."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import psutil

from plantgraph.infra.store_size import read_last_value

#: Neo4j's own name for the metrics file with the fraction of the page cache in use.
PAGE_CACHE_RATIO_FILE = "neo4j.dbms.page_cache.usage_ratio.csv"
PAGE_CACHE_SIZE_SETTING = "server.memory.pagecache.size"

_SIZE_PATTERN = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>[kmgt]?)i?b?", re.IGNORECASE)
_UNIT_BYTES = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}


def process_peak_bytes() -> int:
    """Highest memory this process has held so far (Windows peak working set, POSIX max RSS)."""
    peak_wset = getattr(psutil.Process().memory_info(), "peak_wset", None)
    if peak_wset is not None:
        return int(peak_wset)
    if sys.platform == "win32":
        raise RuntimeError("expected psutil to report peak_wset on Windows, found none")
    import resource  # POSIX only, so imported where it is used

    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes, macOS bytes
    return int(max_rss if sys.platform == "darwin" else max_rss * 1024)


def neo4j_rss_bytes() -> int | None:
    """Resident memory of the largest Java process whose command line mentions neo4j."""
    sizes = [rss for process in psutil.process_iter(["name"]) if (rss := _neo4j_rss(process))]
    return max(sizes, default=None)


def parse_size_bytes(text: str) -> int:
    """Bytes in a Neo4j size setting such as `512m`, `4g` or `4.00GiB`.

    Raises:
        ValueError: the text is not a number with an optional k/m/g/t unit.
    """
    match = _SIZE_PATTERN.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"expected a size such as '512m' or '4.00GiB', found {text!r}")
    return int(float(match["number"]) * _UNIT_BYTES[match["unit"].lower()])


def page_cache_used_bytes(neo4j_home: Path, memory_settings: dict[str, str]) -> int | None:
    """Metrics usage ratio x configured page cache size; `None` if either is missing."""
    ratio = read_last_value(neo4j_home / "metrics" / PAGE_CACHE_RATIO_FILE)
    size = memory_settings.get(PAGE_CACHE_SIZE_SETTING)
    if ratio is None or size is None:
        return None
    return int(ratio * parse_size_bytes(size))


def _neo4j_rss(process: psutil.Process) -> int | None:
    try:
        is_java = "java" in (process.info["name"] or "").lower()
        if not is_java or "neo4j" not in " ".join(process.cmdline()).lower():
            return None
        return int(process.memory_info().rss)
    except psutil.Error:
        return None  # the process ended, or we may not look into it
