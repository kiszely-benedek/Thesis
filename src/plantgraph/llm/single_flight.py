"""One in-flight model call per cache key, so two threads needing the same prompt pay once."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class SingleFlight:
    """Hands out one lock per key; a second thread with the same key waits for the first.

    The waiting thread then finds the first one's response in the cache. Locks are
    dropped when nobody holds or awaits them, so the table stays small.
    """

    def __init__(self) -> None:
        self._table_lock = threading.Lock()
        self._locks: dict[str, tuple[threading.Lock, int]] = {}  # key -> (lock, holders+waiters)

    @contextmanager
    def hold(self, key: str) -> Iterator[None]:
        """Run the body while holding `key`'s lock."""
        lock = self._enter(key)
        try:
            with lock:
                yield
        finally:
            self._leave(key)

    def _enter(self, key: str) -> threading.Lock:
        with self._table_lock:
            lock, users = self._locks.get(key, (threading.Lock(), 0))
            self._locks[key] = (lock, users + 1)
            return lock

    def _leave(self, key: str) -> None:
        with self._table_lock:
            lock, users = self._locks[key]
            if users == 1:
                del self._locks[key]
            else:
                self._locks[key] = (lock, users - 1)
