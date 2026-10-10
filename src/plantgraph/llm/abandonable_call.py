"""Run a blocking call on its own daemon thread, so a caller can stop waiting for it.

A thread cannot be killed from outside, so "abandoning" a model call means the caller
stops waiting while the thread finishes in the background. The thread is a daemon, so
a hung call cannot keep the process alive at exit; it is not a pool worker, so an
abandoned call never takes a slot from the next one.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future


def start_daemon_call[T](call: Callable[[], T]) -> Future[T]:
    """Start `call` on a new daemon thread; the future holds its result or its exception."""
    future: Future[T] = Future()

    def run() -> None:
        try:
            future.set_result(call())
        except BaseException as error:  # noqa: BLE001 - handed to whoever reads the future
            future.set_exception(error)

    threading.Thread(target=run, daemon=True, name="abandonable-model-call").start()
    return future
